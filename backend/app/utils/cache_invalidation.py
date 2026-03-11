"""Centralized cache invalidation helpers.

Call these after any write operation that changes video data, categories, tags,
playlists, chat sessions, preferences, or watch history.
"""

from __future__ import annotations

from app.redis_client import get_redis


def invalidate_video_data(user_id: int) -> None:
    """Invalidate all video-derived caches for a user.

    Call after: sync, delete, categorize, clear-categorizations, delete-by-tags.
    """
    redis = get_redis()

    # Fixed keys
    fixed_keys = [
        f"user_stats:{user_id}",
        f"categories:{user_id}",
        f"tags:{user_id}",
        f"insights:overview:{user_id}",
        f"insights:content_distribution:{user_id}",
        f"insights:temporal:{user_id}",
        f"insights:duration:{user_id}",
    ]
    for key in fixed_keys:
        redis.delete(key)

    # Parameterized keys (e.g. tags:{uid}:50, insights:channels_15:{uid})
    redis.delete_pattern(f"tags:{user_id}:*")
    redis.delete_pattern(f"insights:channels_*:{user_id}")
    redis.delete_pattern(f"insights:recommendations_*:{user_id}")


def invalidate_playlists(user_id: int) -> None:
    """Invalidate playlist list cache for a user."""
    redis = get_redis()
    redis.delete_pattern(f"playlists:{user_id}:*")


def invalidate_chat_sessions(user_id: int) -> None:
    """Invalidate chat session list cache for a user."""
    redis = get_redis()
    redis.delete(f"chat_sessions:{user_id}")


def invalidate_preferences(user_id: int) -> None:
    """Invalidate preferences cache for a user."""
    redis = get_redis()
    redis.delete(f"preferences:{user_id}")


def invalidate_continue_watching(user_id: int) -> None:
    """Invalidate continue-watching cache for a user."""
    redis = get_redis()
    redis.delete_pattern(f"continue_watching:{user_id}:*")
