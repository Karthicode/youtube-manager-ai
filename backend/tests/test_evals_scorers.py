"""Scorer unit tests with canned agent outputs — no DB, no OpenAI."""

from evals.scorers import score_case

CASE = {
    "id": "recent-likes-3",
    "message": "what are my last 3 liked videos?",
    "expected_tools": ["filter_videos"],
    "forbid_tools": ["search_videos"],
    "expected_titles_any": ["Nginx Explained in 10 Minutes"],
    "expect_freshness_caveat": False,
}

GOOD_EVENTS = [
    {
        "tool": "filter_videos",
        "arguments": {"limit": 3},
        "result": [
            {"id": 1, "title": "Nginx Explained in 10 Minutes"},
            {"id": 2, "title": "Canon in D — Piano Cover"},
        ],
    }
]


def test_perfect_run_scores_all_ones() -> None:
    answer = "Your last liked videos include Nginx Explained in 10 Minutes and Canon in D — Piano Cover."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores == {
        "tool_choice": 1.0,
        "groundedness": 1.0,
        "expected_content": 1.0,
        "freshness_caveat": 1.0,
    }


def test_forbidden_tool_fails_tool_choice() -> None:
    events = [{"tool": "search_videos", "arguments": {}, "result": []}]
    scores = score_case(CASE, "anything", events)
    assert scores["tool_choice"] == 0.0


def test_hallucinated_title_fails_groundedness() -> None:
    answer = "You liked 'Totally Invented Video' recently."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores["groundedness"] == 0.0


def test_missing_expected_content() -> None:
    answer = "You liked Canon in D — Piano Cover."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores["expected_content"] == 0.0


def test_freshness_caveat_required_and_present() -> None:
    case = {**CASE, "expect_freshness_caveat": True, "expected_titles_any": []}
    answer = "I found nothing — note your library was last synced on 2026-06-20, so newer likes may be missing."
    scores = score_case(case, answer, GOOD_EVENTS)
    assert scores["freshness_caveat"] == 1.0


def test_freshness_caveat_required_but_absent() -> None:
    case = {**CASE, "expect_freshness_caveat": True, "expected_titles_any": []}
    scores = score_case(case, "You have no videos this week.", GOOD_EVENTS)
    assert scores["freshness_caveat"] == 0.0


def test_hallucinated_title_in_smart_quotes_fails_groundedness() -> None:
    answer = "You liked “Totally Invented Video” recently."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores["groundedness"] == 0.0
