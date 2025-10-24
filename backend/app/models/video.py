from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.category import video_categories
from app.models.tag import video_tags


class Video(Base):
    """Video model for storing YouTube liked videos."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # YouTube video details
    youtube_id = Column(String(20), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    channel_title = Column(String(255), nullable=True)
    channel_id = Column(String(50), nullable=True)

    # Video metadata
    duration_seconds = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)

    # AI categorization status
    is_categorized = Column(Boolean, default=False, nullable=False)
    categorized_at = Column(DateTime, nullable=True)

    # Timestamps
    liked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="videos")
    categories = relationship(
        "Category", secondary=video_categories, back_populates="videos"
    )
    tags = relationship("Tag", secondary=video_tags, back_populates="videos")
    playlist_videos = relationship(
        "PlaylistVideo", back_populates="video", cascade="all, delete-orphan"
    )

    # Composite index for better query performance
    __table_args__ = (
        Index("idx_user_youtube_id", "user_id", "youtube_id", unique=True),
        Index("idx_user_categorized", "user_id", "is_categorized"),
    )
