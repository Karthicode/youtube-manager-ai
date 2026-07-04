"""Sanity checks on the eval dataset files (no DB, no network)."""

from pathlib import Path

import pytest
import yaml

EVALS_DIR = Path(__file__).parent.parent / "evals"
GOLDEN_DATASET = EVALS_DIR / "dataset.yaml"
BEHAVIORAL_DATASET = EVALS_DIR / "dataset-behavioral.yaml"
KNOWN_TOOLS = {
    "search_videos",
    "filter_videos",
    "get_video_stats",
    "create_playlist",
    "get_temporal_trends",
}


def _cases(dataset: Path) -> list[dict]:
    return yaml.safe_load(dataset.read_text())["cases"]


def test_golden_dataset_has_at_least_ten_cases() -> None:
    assert len(_cases(GOLDEN_DATASET)) >= 10


def test_behavioral_dataset_has_eight_cases() -> None:
    assert len(_cases(BEHAVIORAL_DATASET)) == 8


@pytest.mark.parametrize(
    "dataset",
    [GOLDEN_DATASET, BEHAVIORAL_DATASET],
    ids=["golden", "behavioral"],
)
def test_all_cases_well_formed(dataset: Path) -> None:
    seen_ids = set()
    for case in _cases(dataset):
        assert case["id"] not in seen_ids
        seen_ids.add(case["id"])
        assert case["message"].strip()
        assert set(case["expected_tools"]) <= KNOWN_TOOLS
        assert set(case.get("forbid_tools", [])) <= KNOWN_TOOLS
        assert isinstance(case["expected_titles_any"], list)
        assert isinstance(case["expect_freshness_caveat"], bool)


def test_behavioral_cases_are_library_agnostic() -> None:
    """Behavioral cases must not pin specific titles — they run on any library."""
    for case in _cases(BEHAVIORAL_DATASET):
        assert case["expected_titles_any"] == [], case["id"]
