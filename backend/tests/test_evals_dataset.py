"""Sanity checks on the golden dataset file (no DB, no network)."""

from pathlib import Path

import yaml

DATASET = Path(__file__).parent.parent / "evals" / "dataset.yaml"
KNOWN_TOOLS = {
    "search_videos",
    "filter_videos",
    "get_video_stats",
    "create_playlist",
    "get_temporal_trends",
}


def _cases() -> list[dict]:
    return yaml.safe_load(DATASET.read_text())["cases"]


def test_dataset_has_at_least_ten_cases() -> None:
    assert len(_cases()) >= 10


def test_all_cases_well_formed() -> None:
    seen_ids = set()
    for case in _cases():
        assert case["id"] not in seen_ids
        seen_ids.add(case["id"])
        assert case["message"].strip()
        assert set(case["expected_tools"]) <= KNOWN_TOOLS
        assert set(case.get("forbid_tools", [])) <= KNOWN_TOOLS
        assert isinstance(case["expected_titles_any"], list)
        assert isinstance(case["expect_freshness_caveat"], bool)
