"""Auto-categorization service for processing user videos in background."""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.user import User
from app.models.video import Video
from app.config import settings


class AutoCategorizeService:
    """Service for handling automatic video categorization."""

    @staticmethod
    def should_run_for_user(db: Session, user: User) -> tuple[bool, str]:
        """Check if auto-categorization should run for user.

        Returns:
            (should_run, reason_if_skipped)
        """
        # Check if user has preferences
        if not user.preference:
            return False, "No preferences found"

        # Check if auto-categorization is enabled
        if not user.preference.auto_categorize_enabled:
            return False, "Auto-categorization disabled"

        # Check cooldown period (default: 20 hours)
        if user.last_auto_categorize_at:
            cooldown_hours = settings.auto_categorize_cooldown_hours
            cooldown_until = user.last_auto_categorize_at + timedelta(
                hours=cooldown_hours
            )
            if datetime.utcnow() < cooldown_until:
                hours_remaining = (
                    cooldown_until - datetime.utcnow()
                ).total_seconds() / 3600
                return (
                    False,
                    f"Cooldown active (next run in {hours_remaining:.1f} hours)",
                )

        # Check if user has uncategorized videos
        uncategorized_count = (
            db.execute(
                select(Video)
                .where(and_(Video.user_id == user.id, ~Video.is_categorized))
                .limit(1)
            )
            .scalars()
            .first()
        )

        if not uncategorized_count:
            return False, "No uncategorized videos"

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
