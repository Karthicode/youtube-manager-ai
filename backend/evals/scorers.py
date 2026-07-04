"""Deterministic 0/1 scorers for golden-dataset eval runs.

No LLM involvement: every score is computable from the case definition, the
agent's final answer text, and the recorded tool events.
"""

from __future__ import annotations

import re
from typing import Any

# Words that signal the agent acknowledged possibly-stale data.
_FRESHNESS_MARKERS = re.compile(
    r"last sync|synced|out of date|may be missing|not.{0,20}synced|sync.{0,20}dashboard",
    re.IGNORECASE,
)

# Quote characters: straight quotes (", ') and smart/curly quotes (U+2018, U+2019, U+201C, U+201D)
_QUOTE_CHARS = "\"'‘’“”"


def _result_titles(tool_events: list[dict[str, Any]]) -> set[str]:
    titles: set[str] = set()
    for event in tool_events:
        result = event.get("result")
        items = result if isinstance(result, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("title"):
                titles.add(str(item["title"]))
    return titles


def _answer_mentions_unknown_title(answer: str, known_titles: set[str]) -> bool:
    """Heuristic groundedness: quoted/Title-Case runs in the answer must
    appear in some tool result. We check known titles both ways to avoid
    parsing natural language: any known title mentioned is fine; an answer
    that lists 'video'-like quoted strings not in the results is flagged."""
    quoted = re.findall(
        rf"[{_QUOTE_CHARS}]([^{_QUOTE_CHARS}]{{8,90}})[{_QUOTE_CHARS}]", answer
    )
    for candidate in quoted:
        if candidate.strip() and candidate.strip() not in known_titles:
            return True
    return False


def score_case(
    case: dict[str, Any], answer: str, tool_events: list[dict[str, Any]]
) -> dict[str, float]:
    called = [e["tool"] for e in tool_events]

    # 1. Tool choice: at least one expected tool used, no forbidden tool used.
    expected_ok = (not case["expected_tools"]) or any(
        t in called for t in case["expected_tools"]
    )
    forbidden_used = any(t in called for t in case.get("forbid_tools", []))
    tool_choice = 1.0 if expected_ok and not forbidden_used else 0.0

    # 2. Groundedness: known titles referenced must come from tool results.
    known_titles = _result_titles(tool_events)
    grounded = not _answer_mentions_unknown_title(answer, known_titles)
    # Additionally: any expected title claimed must actually be in results.
    for title in case.get("expected_titles_any", []):
        if title in answer and title not in known_titles:
            grounded = False
    groundedness = 1.0 if grounded else 0.0

    # 3. Expected content: at least one expected title in the answer
    #    (vacuously true when none are expected).
    expected_titles = case.get("expected_titles_any", [])
    content_hit = (not expected_titles) or any(t in answer for t in expected_titles)
    expected_content = 1.0 if content_hit else 0.0

    # 4. Freshness caveat present when required (vacuously true otherwise).
    if case.get("expect_freshness_caveat"):
        freshness = 1.0 if _FRESHNESS_MARKERS.search(answer) else 0.0
    else:
        freshness = 1.0

    return {
        "tool_choice": tool_choice,
        "groundedness": groundedness,
        "expected_content": expected_content,
        "freshness_caveat": freshness,
    }
