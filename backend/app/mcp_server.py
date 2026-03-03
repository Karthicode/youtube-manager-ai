"""MCP server exposing the user's video library to MCP-compatible AI tools."""

from __future__ import annotations

import contextvars
import json
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models.category import Category
from app.models.tag import Tag
from app.models.video import Video
from app.services.embedding_service import EmbeddingService
from app.services.profile_service import ProfileService

# Context variable set by auth middleware before MCP tool execution
current_user_id: contextvars.ContextVar[int] = contextvars.ContextVar("current_user_id")

mcp_server = FastMCP(
    name="YouTube Manager AI",
    instructions=(
        "This MCP server provides access to a user's YouTube liked videos library. "
        "You can search videos semantically, browse by category, view recent likes, "
        "get library statistics, and access the user's AI-generated taste profile."
    ),
)


def _get_db() -> Session:
    """Get a new database session for MCP tool handlers."""
    return SessionLocal()


def _get_user_id() -> int:
    """Get the authenticated user ID from context."""
    return current_user_id.get()


def _format_video(video: Video) -> dict:
    """Format a video model into a clean dict for MCP responses."""
    return {
        "id": video.id,
        "youtube_id": video.youtube_id,
        "title": video.title,
        "channel": video.channel_title,
        "duration_seconds": video.duration_seconds,
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "liked_at": video.liked_at.isoformat() if video.liked_at else None,
        "view_count": video.view_count,
        "thumbnail_url": video.thumbnail_url,
        "categories": [c.name for c in video.categories],
        "tags": [t.name for t in video.tags],
        "youtube_url": f"https://www.youtube.com/watch?v={video.youtube_id}",
    }


# --- Tools ---


@mcp_server.tool()
async def search_videos(query: str, limit: int = 10) -> str:
    """Search the user's video library using semantic similarity.

    Finds videos whose content matches the meaning of the query,
    not just keyword matching. Great for finding videos about specific topics.

    Args:
        query: What to search for (e.g. "machine learning tutorials", "cooking pasta")
        limit: Maximum number of results to return (1-50, default 10)
    """
    user_id = _get_user_id()
    limit = max(1, min(50, limit))
    db = _get_db()
    try:
        embedding_service = EmbeddingService()
        results = await embedding_service.search_similar_videos(
            db=db, query=query, user_id=user_id, limit=limit
        )
        formatted = []
        for r in results:
            formatted.append(
                {
                    "title": r["title"],
                    "channel": r["channel_title"],
                    "similarity": r["similarity"],
                    "youtube_url": f"https://www.youtube.com/watch?v={r['youtube_id']}",
                    "categories": [c["name"] for c in r.get("categories", [])],
                    "tags": [t["name"] for t in r.get("tags", [])],
                    "duration_seconds": r.get("duration_seconds"),
                    "liked_at": str(r.get("liked_at", "")),
                }
            )
        return json.dumps({"results": formatted, "total": len(formatted)}, default=str)
    finally:
        db.close()


@mcp_server.tool()
async def get_video_details(video_id: int) -> str:
    """Get full metadata for a specific video by its internal ID.

    Args:
        video_id: The internal video ID (not YouTube ID)
    """
    user_id = _get_user_id()
    db = _get_db()
    try:
        video = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .filter(Video.id == video_id, Video.user_id == user_id)
            .first()
        )
        if not video:
            return json.dumps({"error": f"Video with id {video_id} not found"})
        result = _format_video(video)
        result["description"] = (video.description or "")[:500]
        result["like_count"] = video.like_count
        result["channel_id"] = video.channel_id
        return json.dumps(result, default=str)
    finally:
        db.close()


@mcp_server.tool()
async def get_library_summary() -> str:
    """Get aggregated statistics about the user's video library.

    Returns total videos, top categories, top tags, and the date range of liked videos.
    """
    user_id = _get_user_id()
    db = _get_db()
    try:
        total = db.query(Video).filter(Video.user_id == user_id).count()

        # Top categories
        top_categories = (
            db.query(Category.name, func.count(Video.id).label("count"))
            .join(Video.categories)
            .filter(Video.user_id == user_id)
            .group_by(Category.name)
            .order_by(func.count(Video.id).desc())
            .limit(10)
            .all()
        )

        # Top tags
        top_tags = (
            db.query(Tag.name, func.count(Video.id).label("count"))
            .join(Video.tags)
            .filter(Video.user_id == user_id)
            .group_by(Tag.name)
            .order_by(func.count(Video.id).desc())
            .limit(10)
            .all()
        )

        # Date range
        date_range = (
            db.query(func.min(Video.liked_at), func.max(Video.liked_at))
            .filter(Video.user_id == user_id, Video.liked_at.isnot(None))
            .first()
        )

        # Unique channels
        unique_channels = (
            db.query(func.count(func.distinct(Video.channel_id)))
            .filter(Video.user_id == user_id, Video.channel_id.isnot(None))
            .scalar()
            or 0
        )

        summary = {
            "total_videos": total,
            "unique_channels": unique_channels,
            "top_categories": [
                {"name": name, "count": count} for name, count in top_categories
            ],
            "top_tags": [{"name": name, "count": count} for name, count in top_tags],
            "earliest_liked": (
                str(date_range[0]) if date_range and date_range[0] else None
            ),
            "latest_liked": (
                str(date_range[1]) if date_range and date_range[1] else None
            ),
        }
        return json.dumps(summary, default=str)
    finally:
        db.close()


@mcp_server.tool()
async def get_category_videos(category: str, limit: int = 20) -> str:
    """Get videos from a specific category.

    Args:
        category: Category name (e.g. "Technology", "Music", "Education")
        limit: Maximum number of results (1-50, default 20)
    """
    user_id = _get_user_id()
    limit = max(1, min(50, limit))
    db = _get_db()
    try:
        videos = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .join(Video.categories)
            .filter(Video.user_id == user_id, Category.name.ilike(f"%{category}%"))
            .order_by(Video.liked_at.desc())
            .limit(limit)
            .all()
        )
        result = [_format_video(v) for v in videos]
        return json.dumps(
            {"category": category, "videos": result, "total": len(result)}, default=str
        )
    finally:
        db.close()


@mcp_server.tool()
async def get_recent_videos(days: int = 30, limit: int = 20) -> str:
    """Get recently liked videos.

    Args:
        days: How many days back to look (default 30)
        limit: Maximum number of results (1-50, default 20)
    """
    user_id = _get_user_id()
    limit = max(1, min(50, limit))
    days = max(1, min(365, days))
    db = _get_db()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        videos = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .filter(
                Video.user_id == user_id,
                Video.liked_at.isnot(None),
                Video.liked_at >= cutoff,
            )
            .order_by(Video.liked_at.desc())
            .limit(limit)
            .all()
        )
        result = [_format_video(v) for v in videos]
        return json.dumps(
            {"days": days, "videos": result, "total": len(result)}, default=str
        )
    finally:
        db.close()


@mcp_server.tool()
async def get_taste_profile() -> str:
    """Get the user's AI-generated content taste profile.

    Returns interest clusters, personality tags, consumption style,
    and detected interest drift over time. The profile is cached for 24 hours.
    """
    user_id = _get_user_id()
    db = _get_db()
    try:
        profile_service = ProfileService(user_id=user_id, db=db)
        cached = profile_service.get_cached_profile()
        if cached:
            return json.dumps(cached, default=str)
        return json.dumps(
            {
                "status": "not_available",
                "message": "Taste profile has not been generated yet. "
                "The user needs to generate it from the web app first.",
            }
        )
    finally:
        db.close()


# --- Resources ---


@mcp_server.resource("video-library://categories")
async def list_categories() -> str:
    """List all video categories with counts."""
    user_id = _get_user_id()
    db = _get_db()
    try:
        categories = (
            db.query(Category.name, func.count(Video.id).label("count"))
            .join(Video.categories)
            .filter(Video.user_id == user_id)
            .group_by(Category.name)
            .order_by(func.count(Video.id).desc())
            .all()
        )
        result = [{"name": name, "count": count} for name, count in categories]
        return json.dumps(result)
    finally:
        db.close()


@mcp_server.resource("video-library://tags")
async def list_tags() -> str:
    """List all video tags with counts."""
    user_id = _get_user_id()
    db = _get_db()
    try:
        tags = (
            db.query(Tag.name, func.count(Video.id).label("count"))
            .join(Video.tags)
            .filter(Video.user_id == user_id)
            .group_by(Tag.name)
            .order_by(func.count(Video.id).desc())
            .limit(100)
            .all()
        )
        result = [{"name": name, "count": count} for name, count in tags]
        return json.dumps(result)
    finally:
        db.close()


@mcp_server.resource("video-library://stats")
async def library_stats() -> str:
    """Get library statistics overview."""
    user_id = _get_user_id()
    db = _get_db()
    try:
        total = db.query(Video).filter(Video.user_id == user_id).count()
        categorized = (
            db.query(Video)
            .filter(Video.user_id == user_id, Video.is_categorized.is_(True))
            .count()
        )

        # Embedding stats
        embedding_result = db.execute(
            text(
                """
                SELECT COUNT(embedding) as embedded, COUNT(*) - COUNT(embedding) as not_embedded
                FROM videos WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        embedding_row = embedding_result.fetchone()

        duration_stats = (
            db.query(func.sum(Video.duration_seconds), func.avg(Video.duration_seconds))
            .filter(Video.user_id == user_id, Video.duration_seconds.isnot(None))
            .first()
        )

        unique_channels = (
            db.query(func.count(func.distinct(Video.channel_id)))
            .filter(Video.user_id == user_id, Video.channel_id.isnot(None))
            .scalar()
            or 0
        )

        stats = {
            "total_videos": total,
            "categorized": categorized,
            "uncategorized": total - categorized,
            "embedded": embedding_row.embedded if embedding_row else 0,
            "not_embedded": embedding_row.not_embedded if embedding_row else 0,
            "unique_channels": unique_channels,
            "total_watch_time_seconds": (
                int(duration_stats[0] or 0) if duration_stats else 0
            ),
            "avg_duration_seconds": (
                int(duration_stats[1] or 0) if duration_stats else 0
            ),
        }
        return json.dumps(stats)
    finally:
        db.close()
