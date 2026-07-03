"""Tests for chat agent data-freshness context and recency tool guidance."""

from datetime import datetime, timezone

from app.services.agent_service import AGENT_TOOLS, format_data_freshness


def test_format_data_freshness_includes_both_dates_and_caveat() -> None:
    note = format_data_freshness(
        last_sync_at=datetime(2026, 6, 29, 0, 0, 31, tzinfo=timezone.utc),
        latest_liked_at=datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert "2026-06-29" in note
    assert "2026-06-25" in note
    assert "NOT in the library" in note
    assert "sync" in note.lower()


def test_format_data_freshness_never_synced() -> None:
    note = format_data_freshness(last_sync_at=None, latest_liked_at=None)
    assert "never been synced" in note


def test_format_data_freshness_handles_partial_data() -> None:
    note = format_data_freshness(
        last_sync_at=None,
        latest_liked_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )
    assert "2026-06-25" in note
    assert "NOT in the library" in note


def test_filter_videos_tool_advertises_recency_sorting() -> None:
    filter_tool = next(t for t in AGENT_TOOLS if t["name"] == "filter_videos")
    assert "most recently liked first" in filter_tool["description"]
