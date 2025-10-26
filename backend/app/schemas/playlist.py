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


class FilterParams(BaseModel):
    """Video filter parameters."""

    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None
    search: str | None = None
    is_categorized: bool | None = None


class CreatePlaylistFromFiltersRequest(BaseModel):
    """Request schema for creating a playlist from filtered videos."""

    title: str
    description: str | None = None
    privacy_status: str = "private"  # "private", "unlisted", "public"
    filter_params: FilterParams


class CreatePlaylistFromFiltersResponse(BaseModel):
    """Response schema for playlist creation from filters."""

    playlist: PlaylistResponse
    total_videos: int
    added_immediately: int
    queued_for_background: int
    job_id: str | None = None  # For tracking background progress
