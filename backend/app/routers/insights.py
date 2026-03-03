"""Insights router for analytics and statistics."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, extract
import json
import math

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.schemas.insights import (
    InsightsOverview,
    ContentDistributionResponse,
    CategoryDistribution,
    TagDistribution,
    ChannelsResponse,
    ChannelStats,
    TemporalResponse,
    TemporalData,
    DurationResponse,
    DurationBucket,
    RecommendationsResponse,
    TasteProfileResponse,
)
from app.services.recommendation_service import ChannelRecommendationService
from app.services.profile_service import ProfileService
from app.services.youtube_service import YouTubeService
from app.logger import api_logger
from app.redis_client import get_redis

router = APIRouter(prefix="/insights", tags=["insights"])

# Cache key prefix
CACHE_PREFIX = "insights"
CACHE_TTL = 300  # 5 minutes


def get_cache(user_id: int, key: str) -> dict | None:
    """Get cached data from Redis."""
    redis_client = get_redis()
    data = redis_client.get(f"{CACHE_PREFIX}:{key}:{user_id}")
    return json.loads(data) if data else None


def set_cache(user_id: int, key: str, data: dict, expire: int = CACHE_TTL) -> None:
    """Set cached data in Redis."""
    redis_client = get_redis()
    redis_client.set(
        f"{CACHE_PREFIX}:{key}:{user_id}", json.dumps(data, default=str), expire=expire
    )


@router.get("/overview", response_model=InsightsOverview)
async def get_insights_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get overview statistics for the insights dashboard.

    Returns total counts, unique channels/categories/tags, and date range.
    """
    cache_key = "overview"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            api_logger.debug(
                f"Returning cached insights overview for user {current_user.id}"
            )
            return InsightsOverview(**cached)

    api_logger.info(f"Fetching fresh insights overview for user {current_user.id}")

    # Base query for user's videos
    base_query = db.query(Video).filter(Video.user_id == current_user.id)

    # Total videos
    total_videos = base_query.count()

    # Categorized count
    categorized = base_query.filter(Video.is_categorized.is_(True)).count()
    uncategorized = total_videos - categorized

    # Unique channels
    unique_channels = (
        db.query(func.count(distinct(Video.channel_id)))
        .filter(Video.user_id == current_user.id, Video.channel_id.isnot(None))
        .scalar()
        or 0
    )

    # Unique categories (that have videos)
    unique_categories = (
        db.query(func.count(distinct(Category.id)))
        .join(Video.categories)
        .filter(Video.user_id == current_user.id)
        .scalar()
        or 0
    )

    # Unique tags (that have videos)
    unique_tags = (
        db.query(func.count(distinct(Tag.id)))
        .join(Video.tags)
        .filter(Video.user_id == current_user.id)
        .scalar()
        or 0
    )

    # Total watch time and average duration
    duration_stats = (
        db.query(func.sum(Video.duration_seconds), func.avg(Video.duration_seconds))
        .filter(Video.user_id == current_user.id, Video.duration_seconds.isnot(None))
        .first()
    )

    total_watch_time = int(duration_stats[0] or 0)
    avg_duration = int(duration_stats[1] or 0)

    # Date range
    date_range = (
        db.query(func.min(Video.liked_at), func.max(Video.liked_at))
        .filter(Video.user_id == current_user.id, Video.liked_at.isnot(None))
        .first()
    )

    result = {
        "total_videos": total_videos,
        "categorized": categorized,
        "uncategorized": uncategorized,
        "unique_channels": unique_channels,
        "unique_categories": unique_categories,
        "unique_tags": unique_tags,
        "total_watch_time_seconds": total_watch_time,
        "avg_video_duration_seconds": avg_duration,
        "earliest_liked_at": date_range[0] if date_range else None,
        "latest_liked_at": date_range[1] if date_range else None,
    }

    set_cache(current_user.id, cache_key, result)
    return InsightsOverview(**result)  # type: ignore[arg-type]


@router.get("/content-distribution", response_model=ContentDistributionResponse)
async def get_content_distribution(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get content distribution by categories and tags.

    Returns category breakdown with percentages and tag distribution with weights.
    """
    cache_key = "content_distribution"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            return ContentDistributionResponse(**cached)

    api_logger.info(f"Fetching content distribution for user {current_user.id}")

    # Total categorized videos for percentage calculation
    total_categorized = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, Video.is_categorized.is_(True))
        .count()
    )

    # Category distribution
    category_counts = (
        db.query(Category.name, Category.color, func.count(Video.id).label("count"))
        .join(Video.categories)
        .filter(Video.user_id == current_user.id)
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.count(Video.id).desc())
        .limit(15)
        .all()
    )

    categories = [
        CategoryDistribution(
            name=name,
            count=count,
            percentage=(
                round((count / total_categorized) * 100, 1)
                if total_categorized > 0
                else 0
            ),
            color=color,
        )
        for name, color, count in category_counts
    ]

    # Tag distribution with weights
    tag_counts = (
        db.query(Tag.name, func.count(Video.id).label("count"))
        .join(Video.tags)
        .filter(Video.user_id == current_user.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(Video.id).desc())
        .limit(50)
        .all()
    )

    # Calculate weight (1-5) based on count distribution
    if tag_counts:
        max_count = tag_counts[0][1]
        min_count = tag_counts[-1][1] if len(tag_counts) > 1 else max_count
        count_range = max_count - min_count if max_count != min_count else 1

        tags = [
            TagDistribution(
                name=name,
                count=count,
                weight=min(5, max(1, int(1 + ((count - min_count) / count_range) * 4))),
            )
            for name, count in tag_counts
        ]
    else:
        tags = []

    result = {
        "categories": [c.model_dump() for c in categories],
        "tags": [t.model_dump() for t in tags],
    }

    set_cache(current_user.id, cache_key, result)
    return ContentDistributionResponse(**result)  # type: ignore[arg-type]


@router.get("/channels", response_model=ChannelsResponse)
async def get_channel_insights(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(15, ge=1, le=50, description="Number of top channels to return"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get channel analytics.

    Returns top channels by liked video count and a diversity score.
    """
    cache_key = f"channels_{limit}"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            return ChannelsResponse(**cached)

    api_logger.info(f"Fetching channel insights for user {current_user.id}")

    # Top channels
    channel_stats = (
        db.query(
            Video.channel_title,
            Video.channel_id,
            func.count(Video.id).label("video_count"),
            func.sum(Video.view_count).label("total_views"),
            func.avg(Video.duration_seconds).label("avg_duration"),
        )
        .filter(
            Video.user_id == current_user.id,
            Video.channel_id.isnot(None),
            Video.channel_title.isnot(None),
        )
        .group_by(Video.channel_id, Video.channel_title)
        .order_by(func.count(Video.id).desc())
        .limit(limit)
        .all()
    )

    top_channels = [
        ChannelStats(
            channel_title=title or "Unknown",
            channel_id=channel_id or "",
            video_count=count,
            total_views=int(views or 0),
            avg_duration_seconds=int(avg_dur or 0),
        )
        for title, channel_id, count, views, avg_dur in channel_stats
    ]

    # Total unique channels
    total_channels = (
        db.query(func.count(distinct(Video.channel_id)))
        .filter(Video.user_id == current_user.id, Video.channel_id.isnot(None))
        .scalar()
        or 0
    )

    # Calculate channel diversity score using Shannon entropy
    # Higher score = videos spread across more channels
    total_videos = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, Video.channel_id.isnot(None))
        .count()
    )

    if total_videos > 0 and total_channels > 1:
        # Get all channel counts for entropy calculation
        all_channel_counts = (
            db.query(func.count(Video.id))
            .filter(Video.user_id == current_user.id, Video.channel_id.isnot(None))
            .group_by(Video.channel_id)
            .all()
        )

        # Shannon entropy
        entropy = 0
        for (count,) in all_channel_counts:
            p = count / total_videos
            if p > 0:
                entropy -= p * math.log2(p)

        # Normalize to 0-100 scale (max entropy = log2(n))
        max_entropy = math.log2(total_channels) if total_channels > 1 else 1
        diversity_score = (
            round((entropy / max_entropy) * 100, 1) if max_entropy > 0 else 0
        )
    else:
        diversity_score = 0

    result = {
        "top_channels": [c.model_dump() for c in top_channels],
        "total_channels": total_channels,
        "channel_diversity_score": diversity_score,
    }

    set_cache(current_user.id, cache_key, result)
    return ChannelsResponse(**result)  # type: ignore[arg-type]


@router.get("/temporal", response_model=TemporalResponse)
async def get_temporal_insights(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get temporal patterns of video likes.

    Returns likes distribution by month, day of week, and hour.
    """
    cache_key = "temporal"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            return TemporalResponse(**cached)

    api_logger.info(f"Fetching temporal insights for user {current_user.id}")

    # Likes by month (last 12 months or all available)
    likes_by_month = (
        db.query(
            func.to_char(Video.liked_at, "YYYY-MM").label("month"),
            func.count(Video.id).label("count"),
        )
        .filter(Video.user_id == current_user.id, Video.liked_at.isnot(None))
        .group_by(func.to_char(Video.liked_at, "YYYY-MM"))
        .order_by(func.to_char(Video.liked_at, "YYYY-MM"))
        .all()
    )

    # Likes by day of week (0=Sunday, 6=Saturday)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    likes_by_dow = (
        db.query(
            extract("dow", Video.liked_at).label("dow"),
            func.count(Video.id).label("count"),
        )
        .filter(Video.user_id == current_user.id, Video.liked_at.isnot(None))
        .group_by(extract("dow", Video.liked_at))
        .order_by(extract("dow", Video.liked_at))
        .all()
    )

    # Create full week data (fill in zeros for missing days)
    dow_dict = {int(dow): count for dow, count in likes_by_dow}
    likes_by_day_of_week = [
        TemporalData(label=day_names[i], count=dow_dict.get(i, 0)) for i in range(7)
    ]

    # Likes by hour of day
    likes_by_hour_raw = (
        db.query(
            extract("hour", Video.liked_at).label("hour"),
            func.count(Video.id).label("count"),
        )
        .filter(Video.user_id == current_user.id, Video.liked_at.isnot(None))
        .group_by(extract("hour", Video.liked_at))
        .order_by(extract("hour", Video.liked_at))
        .all()
    )

    # Create full 24 hours (fill in zeros)
    hour_dict = {int(hour): count for hour, count in likes_by_hour_raw}
    likes_by_hour = [
        TemporalData(label=f"{i:02d}:00", count=hour_dict.get(i, 0)) for i in range(24)
    ]

    # Published by year (when videos were originally published)
    published_by_year = (
        db.query(
            extract("year", Video.published_at).label("year"),
            func.count(Video.id).label("count"),
        )
        .filter(Video.user_id == current_user.id, Video.published_at.isnot(None))
        .group_by(extract("year", Video.published_at))
        .order_by(extract("year", Video.published_at))
        .all()
    )

    result = {
        "likes_by_month": [
            TemporalData(label=month, count=count).model_dump()
            for month, count in likes_by_month
        ],
        "likes_by_day_of_week": [d.model_dump() for d in likes_by_day_of_week],
        "likes_by_hour": [h.model_dump() for h in likes_by_hour],
        "published_by_year": [
            TemporalData(label=str(int(year)), count=count).model_dump()
            for year, count in published_by_year
            if year
        ],
    }

    set_cache(current_user.id, cache_key, result)
    return TemporalResponse(**result)  # type: ignore[arg-type]


@router.get("/duration", response_model=DurationResponse)
async def get_duration_insights(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get video duration distribution.

    Returns duration buckets (short, medium, long, very long) with counts.
    """
    cache_key = "duration"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            return DurationResponse(**cached)

    api_logger.info(f"Fetching duration insights for user {current_user.id}")

    # Duration buckets using CASE expression
    from sqlalchemy import case, literal

    duration_case = case(
        (Video.duration_seconds < 300, literal("short")),
        (Video.duration_seconds < 1200, literal("medium")),
        (Video.duration_seconds < 3600, literal("long")),
        else_=literal("very_long"),
    )

    bucket_stats = (
        db.query(
            duration_case.label("bucket"),
            func.count(Video.id).label("count"),
            func.sum(Video.duration_seconds).label("total_seconds"),
        )
        .filter(Video.user_id == current_user.id, Video.duration_seconds.isnot(None))
        .group_by(duration_case)
        .all()
    )

    # Total for percentage calculation
    total_videos = sum(row[1] for row in bucket_stats)

    # Bucket metadata
    bucket_info: dict[str, dict[str, str | int]] = {
        "short": {"label": "Short", "range_label": "< 5 min", "order": 0},
        "medium": {"label": "Medium", "range_label": "5-20 min", "order": 1},
        "long": {"label": "Long", "range_label": "20-60 min", "order": 2},
        "very_long": {"label": "Very Long", "range_label": "> 1 hour", "order": 3},
    }

    # Create buckets dict for easy lookup
    bucket_dict = {
        row[0]: {"count": row[1], "total_seconds": row[2]} for row in bucket_stats
    }

    # Build ordered bucket list
    buckets = []
    for key in ["short", "medium", "long", "very_long"]:
        info = bucket_info[key]
        data = bucket_dict.get(key, {"count": 0, "total_seconds": 0})
        buckets.append(
            DurationBucket(
                label=str(info["label"]),
                range_label=str(info["range_label"]),
                count=data["count"],
                percentage=(
                    round((data["count"] / total_videos) * 100, 1)
                    if total_videos > 0
                    else 0
                ),
                total_seconds=int(data["total_seconds"] or 0),
            )
        )

    # Average duration and total watch time
    duration_stats = (
        db.query(func.avg(Video.duration_seconds), func.sum(Video.duration_seconds))
        .filter(Video.user_id == current_user.id, Video.duration_seconds.isnot(None))
        .first()
    )

    result = {
        "buckets": [b.model_dump() for b in buckets],
        "avg_duration_seconds": int(duration_stats[0] or 0),
        "total_watch_time_seconds": int(duration_stats[1] or 0),
    }

    set_cache(current_user.id, cache_key, result)
    return DurationResponse(**result)  # type: ignore[arg-type]


@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_channel_recommendations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(
        10, ge=1, le=20, description="Maximum number of recommendations"
    ),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get personalized channel recommendations.

    Analyzes user's liked videos to identify preferences (top categories and tags),
    then searches YouTube for similar channels the user doesn't already watch.

    Returns a list of recommended channels with match scores and reasons.
    """
    cache_key = f"recommendations_{limit}"

    if not force_refresh:
        cached = get_cache(current_user.id, cache_key)
        if cached:
            api_logger.debug(
                f"Returning cached recommendations for user {current_user.id}"
            )
            return RecommendationsResponse(**cached)

    api_logger.info(f"Generating fresh recommendations for user {current_user.id}")

    # Initialize services
    youtube_service = YouTubeService(current_user)
    recommendation_service = ChannelRecommendationService(
        user_id=current_user.id,
        db=db,
        youtube_service=youtube_service,
    )

    # Get recommendations
    result = recommendation_service.get_recommendations(limit=limit)

    # Cache the results
    set_cache(current_user.id, cache_key, result)

    return RecommendationsResponse(**result)


@router.get("/taste-profile", response_model=TasteProfileResponse)
async def get_taste_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force regeneration"),
):
    """
    Get the user's content taste profile.

    Returns a cached profile if available, otherwise returns status indicating
    generation is needed.
    """
    profile_service = ProfileService(user_id=current_user.id, db=db)

    if not force_refresh:
        cached = profile_service.get_cached_profile()
        if cached:
            return TasteProfileResponse(**cached)

    # Check video count
    video_count = profile_service.get_video_count()
    if video_count < 20:
        return TasteProfileResponse(
            status="not_available",
            video_count=video_count,
            min_videos_required=20,
        )

    return TasteProfileResponse(
        status="not_available",
        video_count=video_count,
        min_videos_required=20,
    )


@router.post("/taste-profile/generate", response_model=TasteProfileResponse)
async def generate_taste_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Trigger generation of the user's content taste profile.

    This performs k-means clustering on video embeddings, detects interest drift,
    and generates an AI narrative about the user's viewing identity.
    """
    from fastapi import HTTPException, status

    profile_service = ProfileService(user_id=current_user.id, db=db)

    video_count = profile_service.get_video_count()
    if video_count < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Need at least 20 videos with embeddings. Currently have {video_count}.",
        )

    try:
        result = await profile_service.generate_profile()
        return TasteProfileResponse(**result)
    except Exception as e:
        api_logger.error(
            f"Taste profile generation failed for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate taste profile. Please try again.",
        )
