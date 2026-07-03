"""Tests for auto-categorize sync error classification."""

import json
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.services.auto_categorize_service import (
    USER_STATUS_KEY,
    AutoCategorizeService,
)


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


def test_clear_failed_user_status_deletes_key_when_failed() -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps({"status": "failed", "error_type": "auth"})

    with patch(
        "app.services.auto_categorize_service.get_redis", return_value=mock_redis
    ):
        AutoCategorizeService.clear_failed_user_status(42)

    mock_redis.get.assert_called_once_with(USER_STATUS_KEY.format(user_id=42))
    mock_redis.delete.assert_called_once_with(USER_STATUS_KEY.format(user_id=42))


def test_clear_failed_user_status_leaves_non_failed_status() -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps({"status": "triggered"})

    with patch(
        "app.services.auto_categorize_service.get_redis", return_value=mock_redis
    ):
        AutoCategorizeService.clear_failed_user_status(42)

    mock_redis.delete.assert_not_called()


def test_clear_failed_user_status_missing_key_no_error() -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    with patch(
        "app.services.auto_categorize_service.get_redis", return_value=mock_redis
    ):
        AutoCategorizeService.clear_failed_user_status(42)

    mock_redis.delete.assert_not_called()
