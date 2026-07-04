"""Runner plumbing tests via --dry-run (no DB, no OpenAI, no Langfuse)."""

from datetime import datetime, timezone
from pathlib import Path

from evals.run import run_dry

SCORE_KEYS = {
    "tool_choice",
    "groundedness",
    "expected_content",
    "freshness_caveat",
}
BEHAVIORAL_DATASET = Path(__file__).parent.parent / "evals" / "dataset-behavioral.yaml"


def test_dry_run_scores_all_cases() -> None:
    results = run_dry()
    assert len(results) >= 10
    for r in results:
        assert set(r["scores"].keys()) == SCORE_KEYS


def test_dry_run_behavioral_dataset() -> None:
    results = run_dry(dataset_path=BEHAVIORAL_DATASET)
    assert len(results) == 8
    for r in results:
        assert set(r["scores"].keys()) == SCORE_KEYS


def test_inert_user_copy_strips_credentials_and_identity() -> None:
    """The snapshot copy must be unable to act on the real YouTube account
    AND must carry no identifying PII (email, name, picture, channel id)."""
    from app.models.user import User
    from evals.snapshot import _inert_user_copy

    last_sync = datetime(2026, 6, 20, tzinfo=timezone.utc)
    source_user = User(
        id=42,
        email="karthik@gmail.com",
        youtube_id="UC_REAL_USER",
        name="Karthik",
        picture_url="https://example.com/real-face.jpg",
        access_token="ya29.real-access-token",
        refresh_token="1//real-refresh-token",
        api_key="mcp-key-123",
        last_sync_at=last_sync,
    )

    kwargs = _inert_user_copy(source_user)

    assert kwargs["access_token"] is None
    assert kwargs["refresh_token"] is None
    assert kwargs["token_expires_at"] is None
    assert kwargs["api_key"] is None
    # No identifying values survive; pseudonyms are deterministic per source id.
    assert kwargs["email"] == "snapshot-user-42@example.com"
    assert kwargs["youtube_id"] == "snapshot_42"
    assert kwargs["name"] == "Snapshot User"
    assert kwargs["picture_url"] is None
    for value in kwargs.values():
        if isinstance(value, str):
            assert "karthik" not in value.lower()
            assert "UC_REAL_USER" not in value
    assert kwargs["last_sync_at"] == last_sync
    # Sanity: the kwargs must construct a valid User for the eval DB.
    copy = User(**kwargs)
    assert copy.access_token is None and copy.refresh_token is None
