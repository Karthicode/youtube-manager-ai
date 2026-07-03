"""Auto-categorization service for processing user videos in background."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import api_logger
from app.models.user import User
from app.models.video import Video
from app.redis_client import get_redis
from app.services.youtube_service import YouTubeService
from app.utils.qstash_client import trigger_categorization_job

# Redis key for per-user auto-categorize status (7-day TTL).
USER_STATUS_KEY = "auto_categorize:user_status:{user_id}"
USER_STATUS_TTL_SECONDS = 7 * 24 * 60 * 60


class AutoCategorizeService:
    """Service for handling automatic video categorization."""

    @staticmethod
    def should_sync_for_user(user: User) -> tuple[bool, str]:
        """Check if auto-sync+categorize should run for user.

        Validates preferences and cooldown only. Does NOT check for
        uncategorized videos — sync must still run even when the DB is
        caught up so new YouTube likes get pulled in.

        Returns:
            (should_run, reason_if_skipped)
        """
        if not user.preference:
            return False, "No preferences found"

        if not user.preference.auto_categorize_enabled:
            return False, "Auto-categorization disabled"

        if user.last_auto_categorize_at:
            cooldown_hours = settings.auto_categorize_cooldown_hours
            # The column is TIMESTAMP WITHOUT TIME ZONE (see migration
            # 8d9e7f6a5b4c), so SQLAlchemy returns a naive datetime even though
            # we always write UTC. Normalize to tz-aware UTC before comparing
            # against datetime.now(timezone.utc) — otherwise Python raises
            # TypeError ("can't compare offset-naive and offset-aware datetimes")
            # which would escape this function and surface as a 500 on the
            # retry endpoint / a failed user in the cron loop.
            last_run = user.last_auto_categorize_at
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            cooldown_until = last_run + timedelta(hours=cooldown_hours)
            now = datetime.now(timezone.utc)
            if now < cooldown_until:
                hours_remaining = (cooldown_until - now).total_seconds() / 3600
                return (
                    False,
                    f"Cooldown active (next run in {hours_remaining:.1f} hours)",
                )

        return True, ""

    @staticmethod
    def get_uncategorized_videos(
        db: Session, user: User, limit: int | None = None
    ) -> list[Video]:
        """Get uncategorized videos for user.

        Args:
            db: Database session
            user: User object
            limit: Maximum number of videos to return (uses user preference if None)

        Returns:
            List of uncategorized videos
        """
        if limit is None:
            limit = (
                user.preference.auto_categorize_max_videos if user.preference else 50
            )

        videos = (
            db.execute(
                select(Video)
                .where(and_(Video.user_id == user.id, ~Video.is_categorized))
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return list(videos)

    @staticmethod
    def classify_sync_error(exc: Exception) -> str:
        """Classify a sync-stage failure for the dashboard status strip.

        ``auth``: YouTube credentials are expired/revoked (YouTubeService raises
        HTTPException 401 in that case) — the user must reconnect their account.
        ``transient``: anything else — a retry may succeed.
        """
        if isinstance(exc, HTTPException) and exc.status_code == 401:
            return "auth"
        return "transient"

    @staticmethod
    def _write_user_status(user_id: int, data: dict[str, Any]) -> None:
        """Persist per-user status in Redis (7-day TTL). Best-effort."""
        try:
            payload = {
                **data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            get_redis().set(
                USER_STATUS_KEY.format(user_id=user_id),
                json.dumps(payload),
                expire=USER_STATUS_TTL_SECONDS,
            )
        except Exception as e:
            api_logger.warning(
                f"Failed to write auto-categorize user status for {user_id}: {e}"
            )

    @staticmethod
    async def run_for_user(db: Session, user: User) -> dict[str, Any]:
        """Run the sync + categorize flow for a single user.

        Shared core used by both the daily cron loop and the manual retry
        endpoint. Writes per-user status to Redis on every terminal outcome
        so the dashboard banner can surface failures.

        Returns:
            Dict describing the outcome. Always contains ``status`` which is
            one of: ``skipped`` (gate failed), ``no_videos`` (nothing to
            categorize after sync), ``triggered`` (categorization job queued),
            or ``failed`` (exception during sync or QStash trigger).
        """
        should_run, reason = AutoCategorizeService.should_sync_for_user(user)
        if not should_run:
            result: dict[str, Any] = {
                "status": "skipped",
                "reason": reason,
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result

        # Sync latest videos from YouTube before categorizing.
        videos_synced = 0
        try:
            api_logger.info(
                f"Syncing latest {settings.auto_categorize_sync_videos} videos for user {user.id}"
            )
            youtube_service = YouTubeService(user)
            _synced_videos, videos_synced = youtube_service.fetch_liked_videos(
                db, max_results=settings.auto_categorize_sync_videos
            )
            if videos_synced > 0:
                api_logger.info(f"Synced {videos_synced} new videos for user {user.id}")
                user.last_sync_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            api_logger.error(
                f"Failed to sync videos for user {user.id}: {e}", exc_info=True
            )
            result = {
                "status": "failed",
                "stage": "sync",
                "error": str(e),
                "error_type": AutoCategorizeService.classify_sync_error(e),
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result

        # Check for uncategorized videos after sync.
        videos = AutoCategorizeService.get_uncategorized_videos(db, user)
        if not videos:
            result = {
                "status": "no_videos",
                "videos_synced": videos_synced,
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result

        # Trigger categorization job via QStash.
        job_id = str(uuid.uuid4())
        video_ids = [v.id for v in videos]
        try:
            get_redis().set(
                f"categorization_job:{job_id}",
                json.dumps(
                    {
                        "user_id": user.id,
                        "total": len(video_ids),
                        "completed": 0,
                        "failed": 0,
                        "current_video": None,
                        "status": "queued",
                        "paused": False,
                        "results": [],
                    }
                ),
                expire=3600,
            )

            job_result = await trigger_categorization_job(
                job_id=job_id, user_id=user.id, video_ids=video_ids
            )

            if job_result.get("mode") == "error":
                api_logger.error(
                    f"Failed to trigger job for user {user.id}: {job_result}"
                )
                result = {
                    "status": "failed",
                    "stage": "trigger",
                    "videos_synced": videos_synced,
                    "error": str(job_result),
                    "user_id": user.id,
                }
                AutoCategorizeService._write_user_status(user.id, result)
                return result

            user.last_auto_categorize_at = datetime.now(timezone.utc)
            db.commit()

            result = {
                "status": "triggered",
                "videos_synced": videos_synced,
                "videos_categorized": len(videos),
                "job_id": job_id,
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result

        except Exception as e:
            api_logger.error(
                f"Error triggering categorization for user {user.id}: {e}",
                exc_info=True,
            )
            result = {
                "status": "failed",
                "stage": "trigger",
                "videos_synced": videos_synced,
                "error": str(e),
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result

    @staticmethod
    def get_user_status(user_id: int) -> dict[str, Any] | None:
        """Read per-user status from Redis, or None if missing."""
        try:
            raw = get_redis().get(USER_STATUS_KEY.format(user_id=user_id))
            if not raw:
                return None
            return json.loads(raw)
        except Exception as e:
            api_logger.warning(
                f"Failed to read auto-categorize user status for {user_id}: {e}"
            )
            return None
