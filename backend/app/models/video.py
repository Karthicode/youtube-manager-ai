from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base
from app.models.category import video_categories
from app.models.tag import video_tags

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.category import Category
    from app.models.tag import Tag
    from app.models.playlist import PlaylistVideo
    from app.models.watch_history import WatchHistory


class Video(Base):
    """Video model for storing YouTube liked videos."""

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Video source (currently only "liked")
    video_source: Mapped[str] = mapped_column(String(20), default="liked", index=True)

    # YouTube video details
    youtube_id: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    channel_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Video metadata
    duration_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    view_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    like_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    # AI categorization status
    is_categorized: Mapped[bool] = mapped_column(default=False)
    categorized_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Semantic search embedding (1536 dimensions for text-embedding-3-small)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )

    # Timestamps
    liked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="videos")
    categories: Mapped[List["Category"]] = relationship(
        secondary=video_categories, back_populates="videos"
    )
    tags: Mapped[List["Tag"]] = relationship(
        secondary=video_tags, back_populates="videos"
    )
    playlist_videos: Mapped[List["PlaylistVideo"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    watch_history: Mapped[List["WatchHistory"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )

    # Composite index for better query performance
    __table_args__ = (
        Index(
            "idx_user_youtube_id",
            "user_id",
            "youtube_id",
            unique=True,
        ),
        Index("idx_user_categorized", "user_id", "is_categorized"),
        Index("idx_user_source", "user_id", "video_source"),
    )
