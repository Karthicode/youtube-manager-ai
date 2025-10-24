from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class Playlist(Base):
    """Playlist model for storing YouTube playlists."""

    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # YouTube playlist details
    youtube_id = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    channel_title = Column(String(255), nullable=True)
    channel_id = Column(String(50), nullable=True)

    # Playlist metadata
    video_count = Column(Integer, default=0, nullable=False)
    published_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="playlists")
    playlist_videos = relationship(
        "PlaylistVideo", back_populates="playlist", cascade="all, delete-orphan"
    )

    # Composite index
    __table_args__ = (
        Index("idx_user_youtube_playlist", "user_id", "youtube_id", unique=True),
    )


class PlaylistVideo(Base):
    """Association table for playlist-video many-to-many relationship with ordering."""

    __tablename__ = "playlist_videos"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(
        Integer,
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id = Column(
        Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Position in playlist
    position = Column(Integer, nullable=False)

    # Timestamps
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    playlist = relationship("Playlist", back_populates="playlist_videos")
    video = relationship("Video", back_populates="playlist_videos")

    # Composite index
    __table_args__ = (
        Index("idx_playlist_video", "playlist_id", "video_id", unique=True),
        Index("idx_playlist_position", "playlist_id", "position"),
    )
