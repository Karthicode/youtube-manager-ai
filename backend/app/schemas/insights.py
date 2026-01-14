"""Schemas for insights API responses."""

from datetime import datetime
from pydantic import BaseModel


class CategoryDistribution(BaseModel):
    """Category with video count and percentage."""

    name: str
    count: int
    percentage: float
    color: str | None = None


class TagDistribution(BaseModel):
    """Tag with count and weight for visualization."""

    name: str
    count: int
    weight: int  # 1-5 scale for sizing in tag cloud


class ChannelStats(BaseModel):
    """Channel statistics."""

    channel_title: str
    channel_id: str
    video_count: int
    total_views: int
    avg_duration_seconds: int


class TemporalData(BaseModel):
    """Temporal data point for charts."""

    label: str  # Month name, day name, or hour
    count: int


class DurationBucket(BaseModel):
    """Duration distribution bucket."""

    label: str  # "Short", "Medium", "Long", "Very Long"
    range_label: str  # "< 5 min", "5-20 min", etc.
    count: int
    percentage: float
    total_seconds: int


class InsightsOverview(BaseModel):
    """Overview statistics for insights dashboard."""

    total_videos: int
    categorized: int
    uncategorized: int
    unique_channels: int
    unique_categories: int
    unique_tags: int
    total_watch_time_seconds: int
    avg_video_duration_seconds: int
    earliest_liked_at: datetime | None = None
    latest_liked_at: datetime | None = None


class ContentDistributionResponse(BaseModel):
    """Content distribution response."""

    categories: list[CategoryDistribution]
    tags: list[TagDistribution]


class ChannelsResponse(BaseModel):
    """Channels insights response."""

    top_channels: list[ChannelStats]
    total_channels: int
    channel_diversity_score: float  # 0-100, higher = more diverse


class TemporalResponse(BaseModel):
    """Temporal patterns response."""

    likes_by_month: list[TemporalData]
    likes_by_day_of_week: list[TemporalData]
    likes_by_hour: list[TemporalData]
    published_by_year: list[TemporalData]


class DurationResponse(BaseModel):
    """Duration distribution response."""

    buckets: list[DurationBucket]
    avg_duration_seconds: int
    total_watch_time_seconds: int


class ChannelRecommendation(BaseModel):
    """A recommended channel with explanation."""

    channel_id: str
    channel_title: str
    thumbnail_url: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    description: str | None = None
    recommendation_reason: str
    score: float  # 0.0 to 1.0, higher = better match
    source: str  # "content_based" | "youtube_api" | "hybrid"


class RecommendationsResponse(BaseModel):
    """Channel recommendations response."""

    recommendations: list[ChannelRecommendation]
    total_analyzed_channels: int
    top_categories: list[str]
    top_tags: list[str]
