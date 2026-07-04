"""Runner plumbing tests via --dry-run (no DB, no OpenAI, no Langfuse)."""

from evals.run import run_dry


def test_dry_run_scores_all_cases() -> None:
    results = run_dry()
    assert len(results) >= 10
    for r in results:
        assert set(r["scores"].keys()) == {
            "tool_choice",
            "groundedness",
            "expected_content",
            "freshness_caveat",
        }
