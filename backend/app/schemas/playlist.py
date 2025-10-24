from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.video import VideoResponse


class PlaylistBase(BaseModel):
    """Base playlist schema."""

    youtube_id: str
    title: str
    description: str | None = None
    thumbnail_url: str | None = None
    channel_title: str | None = None
    channel_id: str | None = None
    video_count: int = 0
    published_at: datetime | None = None


class PlaylistCreate(PlaylistBase):
    """Schema for creating a playlist."""

    user_id: int


class PlaylistResponse(PlaylistBase):
    """Playlist response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    last_synced_at: datetime | None = None


class PlaylistWithVideos(PlaylistResponse):
    """Playlist with videos."""

    videos: list[VideoResponse] = []


class PlaylistUpdate(BaseModel):
    """Schema for updating playlist."""

    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    video_count: int | None = None
