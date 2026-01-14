from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.video import Video


class Playlist(Base):
    """Playlist model for storing YouTube playlists."""

    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # YouTube playlist details
    youtube_id: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    channel_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Playlist metadata
    video_count: Mapped[int] = mapped_column(default=0)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Soft delete for playlists removed from YouTube

    # Relationships
    user: Mapped["User"] = relationship(back_populates="playlists")
    playlist_videos: Mapped[List["PlaylistVideo"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )

    # Composite index
    __table_args__ = (
        Index("idx_user_youtube_playlist", "user_id", "youtube_id", unique=True),
    )


class PlaylistVideo(Base):
    """Association table for playlist-video many-to-many relationship with ordering."""

    __tablename__ = "playlist_videos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"),
        index=True,
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )

    # Position in playlist
    position: Mapped[int] = mapped_column()

    # Timestamps
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    playlist: Mapped["Playlist"] = relationship(back_populates="playlist_videos")
    video: Mapped["Video"] = relationship(back_populates="playlist_videos")

    # Composite index
    __table_args__ = (
        Index("idx_playlist_video", "playlist_id", "video_id", unique=True),
        Index("idx_playlist_position", "playlist_id", "position"),
    )
