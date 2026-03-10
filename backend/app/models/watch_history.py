from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    String,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.video import Video


class WatchHistory(Base):
    """Watch history model for tracking video playback progress."""

    __tablename__ = "watch_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )

    # Denormalized for join-free dashboard reads
    youtube_id: Mapped[str] = mapped_column(String(20), index=True)

    # Playback state
    position_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    watched_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="watch_history")
    video: Mapped["Video"] = relationship(back_populates="watch_history")

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_watch_history_user_video"),
        Index("idx_wh_user_watched_at", "user_id", "watched_at"),
        Index("idx_wh_user_video", "user_id", "video_id"),
    )
