"""Tests for OAuth `state` signing/verification and origin allowlisting."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.database import get_db
from app.routers.auth import router
from app.services.auth_service import AuthService
from app.services.youtube_service import YouTubeService


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    return TestClient(app)


# --- create_oauth_state / verify_oauth_state -------------------------------


def test_oauth_state_round_trips_valid_origin() -> None:
    state = AuthService.create_oauth_state("http://localhost:4000")
    assert AuthService.verify_oauth_state(state) == "http://localhost:4000"


def test_oauth_state_round_trips_none_origin() -> None:
    state = AuthService.create_oauth_state(None)
    assert AuthService.verify_oauth_state(state) is None


def test_verify_oauth_state_rejects_missing_state() -> None:
    assert AuthService.verify_oauth_state(None) is None
    assert AuthService.verify_oauth_state("") is None


def test_verify_oauth_state_rejects_forged_state() -> None:
    assert AuthService.verify_oauth_state("not-a-real-jwt") is None


def test_verify_oauth_state_rejects_expired_state() -> None:
    expired = jwt.encode(
        {
            "origin": "http://localhost:4000",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "oauth_state",
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert AuthService.verify_oauth_state(expired) is None


def test_verify_oauth_state_rejects_wrong_token_type() -> None:
    # e.g. an access token, which is a validly-signed JWT but not oauth_state
    access_token = AuthService.create_access_token({"sub": "1"})
    assert AuthService.verify_oauth_state(access_token) is None


def test_verify_oauth_state_rejects_disallowed_origin() -> None:
    forged = jwt.encode(
        {
            "origin": "https://evil.example.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            "type": "oauth_state",
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert AuthService.verify_oauth_state(forged) is None


# --- Settings.allowed_origin_regex ------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:4000",
        "http://localhost:3000",  # frontend_url default
    ],
)
def test_allowed_origin_regex_accepts_localhost_and_frontend_url(
    origin: str,
) -> None:
    import re

    assert re.fullmatch(settings.allowed_origin_regex, origin)


@pytest.mark.parametrize(
    "origin",
    [
        "https://youtube-manager-ai.evil.com",
        "https://evil-youtube-manager-ai-hash-team.vercel.app",
        "not-a-url",
    ],
)
def test_allowed_origin_regex_rejects_lookalikes(origin: str) -> None:
    import re

    assert re.fullmatch(settings.allowed_origin_regex, origin) is None


def test_allowed_origin_regex_matches_configured_preview_pattern() -> None:
    import re

    test_settings = settings.model_copy(
        update={
            "frontend_preview_origin_regex": r"https://youtube-manager-ai-[a-z0-9-]+-myteam\.vercel\.app"
        }
    )
    assert re.fullmatch(
        test_settings.allowed_origin_regex,
        "https://youtube-manager-ai-git-my-branch-myteam.vercel.app",
    )
    assert (
        re.fullmatch(
            test_settings.allowed_origin_regex,
            "https://youtube-manager-ai-git-my-branch-otherteam.vercel.app",
        )
        is None
    )


# --- get_youtube_authorization_url / router endpoints -----------------------


def test_get_youtube_authorization_url_signs_allowed_origin() -> None:
    auth_url = AuthService.get_youtube_authorization_url(origin="http://localhost:4000")
    state = parse_qs(urlparse(auth_url).query)["state"][0]
    assert AuthService.verify_oauth_state(state) == "http://localhost:4000"


def test_get_youtube_authorization_url_drops_disallowed_origin() -> None:
    auth_url = AuthService.get_youtube_authorization_url(
        origin="https://evil.example.com"
    )
    state = parse_qs(urlparse(auth_url).query)["state"][0]
    assert AuthService.verify_oauth_state(state) is None


def test_youtube_login_endpoint_returns_signed_state() -> None:
    client = _make_client()
    response = client.get(
        "/auth/youtube/login", params={"origin": "http://localhost:4000"}
    )
    assert response.status_code == 200
    auth_url = response.json()["auth_url"]
    state = parse_qs(urlparse(auth_url).query)["state"][0]
    assert AuthService.verify_oauth_state(state) == "http://localhost:4000"


def test_youtube_callback_redirects_to_origin_from_state() -> None:
    client = _make_client()
    state = AuthService.create_oauth_state("http://localhost:4000")

    fake_user = SimpleNamespace(
        id=1,
        email="user@example.com",
        name="Test User",
        picture_url=None,
        youtube_id="UC123",
        last_sync_at=None,
    )

    with (
        patch.object(
            AuthService,
            "exchange_youtube_code_for_tokens",
            return_value=SimpleNamespace(token="access", refresh_token="refresh"),
        ),
        patch.object(YouTubeService, "_initialize_client", return_value=None),
        patch.object(YouTubeService, "get_user_info", return_value={"id": "UC123"}),
        patch.object(
            AuthService, "get_or_create_user_from_youtube", return_value=fake_user
        ),
        patch.object(
            AuthService,
            "create_tokens_for_user",
            return_value={"access_token": "jwt-access", "refresh_token": "jwt-refresh"},
        ),
    ):
        response = client.get(
            "/auth/youtube/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:4000/auth/callback")


def test_youtube_callback_falls_back_to_frontend_url_on_missing_state() -> None:
    client = _make_client()

    fake_user = SimpleNamespace(
        id=1,
        email="user@example.com",
        name="Test User",
        picture_url=None,
        youtube_id="UC123",
        last_sync_at=None,
    )

    with (
        patch.object(
            AuthService,
            "exchange_youtube_code_for_tokens",
            return_value=SimpleNamespace(token="access", refresh_token="refresh"),
        ),
        patch.object(YouTubeService, "_initialize_client", return_value=None),
        patch.object(YouTubeService, "get_user_info", return_value={"id": "UC123"}),
        patch.object(
            AuthService, "get_or_create_user_from_youtube", return_value=fake_user
        ),
        patch.object(
            AuthService,
            "create_tokens_for_user",
            return_value={"access_token": "jwt-access", "refresh_token": "jwt-refresh"},
        ),
    ):
        response = client.get(
            "/auth/youtube/callback",
            params={"code": "auth-code"},
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith(f"{settings.frontend_url}/auth/callback")
