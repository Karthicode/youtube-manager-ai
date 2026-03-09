"""Cron job endpoints triggered by QStash scheduled messages."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.user_preference import UserPreference
from app.redis_client import redis_client
from app.services.auto_categorize_service import AutoCategorizeService
from app.logger import api_logger
from app.utils.qstash_client import trigger_categorization_job

router = APIRouter(prefix="/cron", tags=["cron"])

# Redis keys for tracking
LAST_RUN_KEY = "auto_categorize:last_run"
RUN_HISTORY_KEY = "auto_categorize:run_history:{date}"


def set_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set job data in Redis with expiration (default 1 hour)."""
    redis_client.set(f"categorization_job:{job_id}", json.dumps(data), expire=expire)


@router.get("/auto-categorize/status")
async def get_auto_categorize_status() -> dict[str, Any]:
    """
    Get the status of the last auto-categorization run.

    Returns stats from the most recent run if available.
    """
    try:
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


@router.post("/auto-categorize")
async def auto_categorize_all_users(
    db: Session = Depends(get_db),
    x_cron_secret: str | None = Header(None, alias="x-cron-secret"),
) -> dict[str, Any]:
    """
    Triggered daily at midnight UTC via QStash scheduled message.

    Protected by cron_secret token (set in env variables).
    Processes all users with auto_categorize_enabled=True sequentially.
    """
    # Verify cron secret
    if not settings.cron_secret_token:
        raise HTTPException(
            status_code=500, detail="Cron secret token not configured on server"
        )

    if x_cron_secret != settings.cron_secret_token:
        api_logger.warning(
            f"Unauthorized cron attempt with secret: {x_cron_secret[:10] if x_cron_secret else 'None'}..."
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Check if auto-categorization is globally enabled
    if not settings.auto_categorize_enabled:
        api_logger.info("Auto-categorization is globally disabled")
        return {
            "status": "skipped",
            "reason": "Auto-categorization globally disabled",
            "timestamp": datetime.utcnow().isoformat(),
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
        "total_videos": 0,
        "jobs_triggered": 0,
        "skip_reasons": {},
    }

    # Process each user sequentially with delay
    for user in users:
        try:
            # Check if should run for this user
            should_run, reason = AutoCategorizeService.should_run_for_user(db, user)

            if not should_run:
                stats["skipped"] += 1
                stats["skip_reasons"][reason] = stats["skip_reasons"].get(reason, 0) + 1
                api_logger.info(f"Skipping user {user.id}: {reason}")
                continue

            # Get uncategorized videos
            videos = AutoCategorizeService.get_uncategorized_videos(db, user)

            if not videos:
                stats["skipped"] += 1
                stats["skip_reasons"]["No uncategorized videos"] = (
                    stats["skip_reasons"].get("No uncategorized videos", 0) + 1
                )
                api_logger.info(f"Skipping user {user.id}: No uncategorized videos")
                continue

            # Generate unique job ID
            job_id = str(uuid.uuid4())

            # Initialize job data in Redis (required for worker)
            video_ids = [v.id for v in videos]
            set_job_data(
                job_id,
                {
                    "user_id": user.id,
                    "total": len(video_ids),
                    "completed": 0,
                    "failed": 0,
                    "current_video": None,
                    "status": "queued",
                    "paused": False,
                    "results": [],
                },
            )

            # Trigger QStash categorization job
            job_result = await trigger_categorization_job(
                job_id=job_id, user_id=user.id, video_ids=video_ids
            )

            # Check if QStash trigger failed
            if job_result.get("mode") == "error":
                stats["failed"] += 1
                api_logger.error(
                    f"Failed to trigger job for user {user.id}: {job_result}"
                )
                continue

            # Update last_auto_categorize_at timestamp
            user.last_auto_categorize_at = datetime.utcnow()
            db.commit()

            stats["processed"] += 1
            stats["total_videos"] += len(videos)
            stats["jobs_triggered"] += 1

            api_logger.info(
                f"Triggered categorization job for user {user.id}: "
                f"{len(videos)} videos, job_id={job_id}"
            )

            # Add delay before processing next user
            if settings.auto_categorize_user_delay_seconds > 0:
                await asyncio.sleep(settings.auto_categorize_user_delay_seconds)

        except Exception as e:
            stats["failed"] += 1
            api_logger.error(f"Error processing user {user.id}: {e}", exc_info=True)
            # Continue to next user even if one fails
            continue

    api_logger.info(f"Auto-categorization cron job completed: {stats}")

    # Store stats in Redis for monitoring
    run_data = {
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat(),
        "stats": stats,
    }

    try:
        # Store as latest run (no expiry)
        redis_client.set(LAST_RUN_KEY, json.dumps(run_data))

        # Store in daily history (7 day expiry)
        date_key = RUN_HISTORY_KEY.format(date=datetime.utcnow().strftime("%Y-%m-%d"))
        redis_client.set(date_key, json.dumps(run_data), expire=7 * 24 * 60 * 60)

        api_logger.info("Auto-categorization stats saved to Redis")
    except Exception as e:
        api_logger.warning(f"Failed to save stats to Redis: {e}")

    return run_data
