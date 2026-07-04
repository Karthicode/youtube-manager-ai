"""Golden-dataset eval runner for the chat agent.

Usage:
    poetry run python -m evals.run            # real run (docker DB + OpenAI)
    poetry run python -m evals.run --dry-run  # scorer plumbing check, no I/O

Real runs execute each case against the actual AgentService on the seeded
eval library, score deterministically, print a table, and upload the run to
Langfuse via run_experiment (when Langfuse keys are configured).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path
from typing import Any

import yaml

DATASET_PATH = Path(__file__).parent / "dataset.yaml"


def load_cases() -> list[dict[str, Any]]:
    cases = yaml.safe_load(DATASET_PATH.read_text())["cases"]
    messages = [c["message"] for c in cases]
    assert len(set(messages)) == len(messages), "dataset case messages must be unique"
    return cases


def run_dry() -> list[dict[str, Any]]:
    """Score canned outputs for every case — validates plumbing, not the agent."""
    from evals.scorers import score_case

    results = []
    for case in load_cases():
        canned_events = [
            {
                "tool": (case["expected_tools"] or ["filter_videos"])[0],
                "arguments": {},
                "result": [{"id": 1, "title": t} for t in case["expected_titles_any"]],
            }
        ]
        canned_answer = " ".join(case["expected_titles_any"]) or (
            "Nothing found — note your library was last synced recently; "
            "newer likes may be missing until you sync."
        )
        results.append(
            {
                "id": case["id"],
                "scores": score_case(case, canned_answer, canned_events),
            }
        )
    return results


async def _run_case(agent, case: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Drive one chat turn; collect final text + tool events.

    The agent yields a ``ChatStreamEvent`` whose final-answer text arrives as
    ``type="message"`` with ``content=final_text`` (see agent_service.py,
    the synthesis-yield right before ``type="done"``). The ``elif
    event.content:`` branch below picks that up (and also an ``type="error"``
    event, which also carries text) without needing to special-case the type.
    """
    session_id = str(uuid.uuid4())
    answer_parts: list[str] = []
    tool_events: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    async for event in agent.chat(session_id, case["message"]):
        if event.type == "tool_call":
            pending[event.tool] = {"tool": event.tool, "arguments": event.arguments}
        elif event.type == "tool_result":
            entry = pending.pop(event.tool, {"tool": event.tool, "arguments": {}})
            entry["result"] = event.result
            tool_events.append(entry)
        elif event.content:
            answer_parts.append(event.content)
    return "".join(answer_parts), tool_events


def run_real() -> list[dict[str, Any]]:
    from app.services.agent_service import AgentService
    from evals.db import create_schema, get_eval_session
    from evals.scorers import score_case
    from evals.seed import seed

    create_schema()
    db = get_eval_session()
    try:
        user_id = seed(db)
        results = []
        for case in load_cases():
            agent = AgentService(user_id=user_id, db=db)
            try:
                answer, tool_events = asyncio.run(_run_case(agent, case))
            except Exception as e:
                # A crashed turn is evidence, not a run-stopper: score it as
                # a real FAIL and keep going.
                answer, tool_events = f"[eval runner error] {e}", []
            scores = score_case(case, answer, tool_events)
            results.append(
                {
                    "id": case["id"],
                    "message": case["message"],
                    "answer": answer,
                    "tool_events": tool_events,
                    "scores": scores,
                }
            )
            flags = " ".join(
                f"{k}={'PASS' if v else 'FAIL'}" for k, v in scores.items()
            )
            print(f"[{case['id']}] {flags}")
        _print_summary(results)
        try:
            _upload_to_langfuse(results)
        except Exception as e:
            print(f"Langfuse upload failed — summary above is still valid: {e}")
        return results
    finally:
        db.close()


def _print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    for metric in (
        "tool_choice",
        "groundedness",
        "expected_content",
        "freshness_caveat",
    ):
        passed = sum(1 for r in results if r["scores"][metric] == 1.0)
        print(f"{metric}: {passed}/{total}")


def _upload_to_langfuse(results: list[dict[str, Any]]) -> None:
    """Upload as a Langfuse DATASET RUN so runs are comparable across versions.

    (Local-data run_experiment creates only traces, no dataset runs — the spec
    requires run-over-run score history, hence the dataset sync first.)
    Skipped without keys.
    """
    from datetime import datetime, timezone

    from app.observability import get_langfuse

    client = get_langfuse()
    if client is None:
        print("Langfuse not configured — skipping experiment upload.")
        return
    from langfuse import Evaluation

    dataset_name = "chat-agent-golden"
    try:
        client.create_dataset(name=dataset_name)
    except Exception as e:
        print(f"create_dataset: {e} (continuing — likely already exists)")
    for r in results:
        # Deterministic id makes re-runs upsert instead of duplicating items.
        client.create_dataset_item(
            dataset_name=dataset_name,
            id=f"golden-{r['id']}",
            input=r["message"],
            metadata={"case_id": r["id"]},
        )

    # Keyed by case_id (not message text) to avoid silent collisions if two
    # cases ever share a message. Confirmed via SDK source (langfuse 4.13.0,
    # langfuse/_client/client.py::_process_experiment_item) that
    # dataset.run_experiment() calls each evaluator with
    # metadata=item.metadata — i.e. the dataset item's own metadata dict,
    # which we set to {"case_id": ...} above — so evaluators can key off
    # metadata["case_id"] directly.
    by_case_id = {r["id"]: r for r in results}

    def task(*, item, **kwargs):
        return by_case_id[item.metadata["case_id"]]["answer"]

    def make_evaluator(metric: str):
        def evaluator(*, input, output, metadata, **kwargs):
            return Evaluation(
                name=metric, value=by_case_id[metadata["case_id"]]["scores"][metric]
            )

        evaluator.__name__ = f"{metric}_evaluator"
        return evaluator

    dataset = client.get_dataset(dataset_name)
    run_name = f"golden-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    result = dataset.run_experiment(
        name=run_name,
        description="Deterministic golden-dataset run",
        task=task,
        evaluators=[
            make_evaluator(m)
            for m in (
                "tool_choice",
                "groundedness",
                "expected_content",
                "freshness_caveat",
            )
        ],
    )
    print(result.format())
    client.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        for r in run_dry():
            print(r["id"], r["scores"])
    else:
        run_real()
