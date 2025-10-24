from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.category import CategoryResponse
from app.schemas.tag import TagResponse


class VideoBase(BaseModel):
    """Base video schema."""

    youtube_id: str
    title: str
    description: str | None = None
    thumbnail_url: str | None = None
    channel_title: str | None = None
    channel_id: str | None = None
    duration_seconds: int | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None


class VideoCreate(VideoBase):
    """Schema for creating a video."""

    user_id: int
    liked_at: datetime | None = None


class VideoResponse(VideoBase):
    """Video response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_categorized: bool
    categorized_at: datetime | None = None
    liked_at: datetime | None = None
    created_at: datetime
    categories: list[CategoryResponse] = []
    tags: list[TagResponse] = []


class VideoUpdate(BaseModel):
    """Schema for updating video."""

    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None


class VideoFilter(BaseModel):
    """Schema for filtering videos."""

    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None
    search_query: str | None = None
    min_duration: int | None = None
    max_duration: int | None = None
    published_after: datetime | None = None
    published_before: datetime | None = None
    is_categorized: bool | None = None


class VideoSort(BaseModel):
    """Schema for sorting videos."""

    sort_by: str = "liked_at"  # liked_at, title, duration, published_at, view_count
    sort_order: str = "desc"  # asc, desc


class PaginatedVideosResponse(BaseModel):
    """Paginated response for videos."""

    items: list[VideoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
