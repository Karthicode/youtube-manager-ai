"""Service for watch history / continue watching functionality."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logger import app_logger
from app.models.video import Video
from app.models.watch_history import WatchHistory
from app.schemas.watch_history import WatchHistoryResponse

_COMPLETED_THRESHOLD = 90.0  # percent
_MIN_POSITION_SECONDS = 10.0  # skip saves below this


def _build_response(entry: WatchHistory, video: Video) -> WatchHistoryResponse:
    return WatchHistoryResponse(
        id=entry.id,
        video_id=entry.video_id,
        youtube_id=entry.youtube_id,
        title=video.title,
        thumbnail_url=video.thumbnail_url,
        channel_title=video.channel_title,
        position_seconds=entry.position_seconds,
        duration_seconds=entry.duration_seconds,
        progress_percent=entry.progress_percent,
        is_completed=entry.is_completed,
        watched_at=entry.watched_at,
        created_at=entry.created_at,
    )


def upsert_position(
    db: Session,
    user_id: int,
    youtube_id: str,
    position_seconds: float,
    duration_seconds: Optional[int],
) -> Optional[WatchHistoryResponse]:
    """Save (or update) the playback position for a video."""
    if position_seconds < _MIN_POSITION_SECONDS:
        return None

    # Look up the video owned by this user
    video_result = db.execute(
        select(Video).where(
            Video.user_id == user_id,
            Video.youtube_id == youtube_id,
        )
    )
    video = video_result.scalar_one_or_none()
    if video is None:
        app_logger.warning(
            f"upsert_position: video {youtube_id} not found for user {user_id}"
        )
        return None

    # Use provided duration or fall back to what we have on the video row
    effective_duration = duration_seconds or video.duration_seconds

    # Compute progress
    progress_percent = 0.0
    if effective_duration and effective_duration > 0:
        progress_percent = min((position_seconds / effective_duration) * 100.0, 100.0)
    is_completed = progress_percent >= _COMPLETED_THRESHOLD

    # Upsert
    entry_result = db.execute(
        select(WatchHistory).where(
            WatchHistory.user_id == user_id,
            WatchHistory.video_id == video.id,
        )
    )
    entry = entry_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if entry is None:
        entry = WatchHistory(
            user_id=user_id,
            video_id=video.id,
            youtube_id=youtube_id,
            position_seconds=position_seconds,
            duration_seconds=effective_duration,
            progress_percent=progress_percent,
            is_completed=is_completed,
            watched_at=now,
            created_at=now,
        )
        db.add(entry)
    else:
        entry.position_seconds = position_seconds
        entry.duration_seconds = effective_duration
        entry.progress_percent = progress_percent
        entry.is_completed = is_completed
        entry.watched_at = now

    db.commit()
    db.refresh(entry)
    return _build_response(entry, video)


def get_continue_watching(
    db: Session,
    user_id: int,
    limit: int = 10,
) -> List[WatchHistoryResponse]:
    """Return in-progress (not completed) videos ordered by most recently watched."""
    result = db.execute(
        select(WatchHistory, Video)
        .join(Video, WatchHistory.video_id == Video.id)
        .where(
            WatchHistory.user_id == user_id,
            WatchHistory.is_completed == False,  # noqa: E712
        )
        .order_by(WatchHistory.watched_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [_build_response(entry, video) for entry, video in rows]


def get_position(
    db: Session,
    user_id: int,
    youtube_id: str,
) -> Optional[WatchHistoryResponse]:
    """Return the saved position for a specific video."""
    result = db.execute(
        select(WatchHistory, Video)
        .join(Video, WatchHistory.video_id == Video.id)
        .where(
            WatchHistory.user_id == user_id,
            WatchHistory.youtube_id == youtube_id,
        )
    )
    row = result.first()
    if row is None:
        return None
    entry, video = row
    return _build_response(entry, video)


def delete_history_entry(
    db: Session,
    user_id: int,
    history_id: int,
) -> None:
    """Delete a watch history entry (ownership check included)."""
    result = db.execute(
        select(WatchHistory).where(
            WatchHistory.id == history_id,
            WatchHistory.user_id == user_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Watch history entry not found")
    db.delete(entry)
    db.commit()
