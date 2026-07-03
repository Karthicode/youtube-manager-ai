"""Tests for auto-categorize sync error classification."""

from fastapi import HTTPException

from app.services.auto_categorize_service import AutoCategorizeService


def test_classify_sync_error_auth_for_401_http_exception() -> None:
    exc = HTTPException(
        status_code=401,
        detail="YouTube authentication expired. Please reconnect your account.",
    )
    assert AutoCategorizeService.classify_sync_error(exc) == "auth"


def test_classify_sync_error_transient_for_generic_exception() -> None:
    assert (
        AutoCategorizeService.classify_sync_error(RuntimeError("boom")) == "transient"
    )


def test_classify_sync_error_transient_for_non_401_http_exception() -> None:
    exc = HTTPException(status_code=500, detail="upstream error")
    assert AutoCategorizeService.classify_sync_error(exc) == "transient"
