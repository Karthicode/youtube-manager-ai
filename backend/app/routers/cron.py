"""Cron job endpoints triggered by QStash scheduled messages."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from qstash import Receiver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.logger import api_logger
from app.models.user import User
from app.models.user_preference import UserPreference
from app.redis_client import get_redis
from app.services.auto_categorize_service import AutoCategorizeService

router = APIRouter(prefix="/cron", tags=["cron"])

# Redis keys for tracking the aggregate cron run.
LAST_RUN_KEY = "auto_categorize:last_run"
RUN_HISTORY_KEY = "auto_categorize:run_history:{date}"


@router.get("/auto-categorize/status")
async def get_auto_categorize_status() -> dict[str, Any]:
    """
    Get the status of the last auto-categorization run (aggregate across all users).
    """
    try:
        redis_client = get_redis()
        last_run_data = redis_client.get(LAST_RUN_KEY)

        if not last_run_data:
            return {
                "status": "no_runs",
                "message": "No auto-categorization runs found",
            }

        return json.loads(last_run_data)

    except Exception as e:
        api_logger.error(f"Failed to retrieve auto-categorization status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve auto-categorization status",
        )


@router.get("/auto-categorize/status/me")
async def get_my_auto_categorize_status(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Per-user status from the most recent auto-categorize attempt.

    Returns ``{"status": "no_runs"}`` when nothing has been recorded for this
    user yet (e.g., first login, or Redis entry expired after 7 days).
    """
    data = AutoCategorizeService.get_user_status(current_user.id)
    if data is None:
        return {"status": "no_runs"}
    return data


@router.post("/auto-categorize")
async def auto_categorize_all_users(
    request: Request,
    db: Session = Depends(get_db),
    upstash_signature: str | None = Header(None, alias="Upstash-Signature"),
) -> dict[str, Any]:
    """
    Triggered daily at midnight UTC via QStash scheduled message.

    Protected by QStash signature verification.
    Processes all users with auto_categorize_enabled=True sequentially.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify QStash signature
    if settings.qstash_token and settings.qstash_current_signing_key:
        try:
            if not upstash_signature:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing signature",
                )

            receiver = Receiver(
                current_signing_key=settings.qstash_current_signing_key,
                next_signing_key=settings.qstash_next_signing_key,
            )

            # Construct the full URL for verification
            base_url = settings.backend_url.rstrip("/")
            full_url = f"{base_url}/api/v1/cron/auto-categorize"

            # Verify the signature
            receiver.verify(
                signature=upstash_signature,
                body=body.decode("utf-8"),
                url=full_url,
            )
            api_logger.info("QStash signature verified successfully for cron job")
        except Exception as e:
            api_logger.error(f"QStash signature verification failed for cron: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )
    else:
        api_logger.warning(
            "QStash signature verification skipped (keys not configured)"
        )

    # Check if auto-categorization is globally enabled
    if not settings.auto_categorize_enabled:
        api_logger.info("Auto-categorization is globally disabled")
        return {
            "status": "skipped",
            "reason": "Auto-categorization globally disabled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    api_logger.info("Starting auto-categorization cron job")

    # Query all users with auto_categorize_enabled=True
    result = db.execute(
        select(User)
        .join(UserPreference)
        .where(UserPreference.auto_categorize_enabled == True)  # noqa: E712
    )
    users = result.scalars().all()

    api_logger.info(f"Found {len(users)} users with auto-categorization enabled")

    # Stats tracking
    stats: dict[str, Any] = {
        "total_users": len(users),
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "total_videos_synced": 0,
        "total_videos_categorized": 0,
        "jobs_triggered": 0,
        "skip_reasons": {},
    }

    # Process each user sequentially with delay
    for user in users:
        try:
            user_result = await AutoCategorizeService.run_for_user(db, user)
        except Exception as e:
            # Defensive: run_for_user catches internally, but in case of bugs
            # we still want the loop to continue.
            stats["failed"] += 1
            api_logger.error(
                f"Unexpected error processing user {user.id}: {e}", exc_info=True
            )
            continue

        videos_synced = user_result.get("videos_synced", 0) or 0
        stats["total_videos_synced"] += videos_synced

        status_value = user_result.get("status")
        if status_value == "skipped":
            stats["skipped"] += 1
            reason = user_result.get("reason", "unknown")
            stats["skip_reasons"][reason] = stats["skip_reasons"].get(reason, 0) + 1
            api_logger.info(f"Skipping user {user.id}: {reason}")
        elif status_value == "no_videos":
            stats["skipped"] += 1
            reason = "No uncategorized videos"
            stats["skip_reasons"][reason] = stats["skip_reasons"].get(reason, 0) + 1
            api_logger.info(f"User {user.id}: {reason} after sync")
        elif status_value == "triggered":
            stats["processed"] += 1
            stats["jobs_triggered"] += 1
            stats["total_videos_categorized"] += user_result.get(
                "videos_categorized", 0
            )
            api_logger.info(
                f"Triggered categorization job for user {user.id}: "
                f"{user_result.get('videos_categorized', 0)} videos, "
                f"job_id={user_result.get('job_id')}"
            )
        elif status_value == "failed":
            stats["failed"] += 1
            api_logger.error(
                f"Failed to process user {user.id} at stage "
                f"{user_result.get('stage')}: {user_result.get('error')}"
            )

        # Add delay before processing next user
        if settings.auto_categorize_user_delay_seconds > 0:
            await asyncio.sleep(settings.auto_categorize_user_delay_seconds)

    api_logger.info(f"Auto-categorization cron job completed: {stats}")

    # Store stats in Redis for monitoring
    run_data = {
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
    }

    try:
        redis_client = get_redis()
        # Store as latest run (no expiry)
        redis_client.set(LAST_RUN_KEY, json.dumps(run_data))

        # Store in daily history (7 day expiry)
        date_key = RUN_HISTORY_KEY.format(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        redis_client.set(date_key, json.dumps(run_data), expire=7 * 24 * 60 * 60)

        api_logger.info("Auto-categorization stats saved to Redis")
    except Exception as e:
        api_logger.warning(f"Failed to save stats to Redis: {e}")

    return run_data
