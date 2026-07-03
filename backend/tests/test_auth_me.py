"""Tests for the GET /auth/me endpoint."""

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.routers.auth import router


def _make_client(user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_get_me_returns_frontend_user_shape() -> None:
    user = SimpleNamespace(
        id=3,
        email="user@example.com",
        name="Test User",
        picture_url="https://example.com/pic.jpg",
        youtube_id="UC123",
        last_sync_at=datetime(2026, 6, 29, 0, 0, 31, tzinfo=timezone.utc),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    response = _make_client(user).get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 3
    assert body["email"] == "user@example.com"
    assert body["name"] == "Test User"
    # Field names must match the frontend User type / OAuth callback payload.
    assert body["picture"] == "https://example.com/pic.jpg"
    assert body["youtube_channel_id"] == "UC123"
    assert body["last_sync_at"].startswith("2026-06-29")
    assert body["created_at"].startswith("2025-01-01")


def test_get_me_handles_nullable_fields() -> None:
    user = SimpleNamespace(
        id=4,
        email="bare@example.com",
        name=None,
        picture_url=None,
        youtube_id="UC456",
        last_sync_at=None,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    response = _make_client(user).get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] is None
    assert body["picture"] is None
    assert body["last_sync_at"] is None
