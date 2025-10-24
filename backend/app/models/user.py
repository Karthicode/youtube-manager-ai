from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User model for storing YouTube account information."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    youtube_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    picture_url = Column(String(512), nullable=True)

    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_sync_at = Column(DateTime, nullable=True)

    # Relationships
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship(
        "Playlist", back_populates="user", cascade="all, delete-orphan"
    )
