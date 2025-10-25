"""Progress tracking service for long-running tasks."""

from typing import Dict, Any
from app.services.redis_client import get_redis_client
from app.logger import api_logger
import json


class ProgressService:
    """Service for tracking progress of categorization tasks."""

    @staticmethod
    def set_progress(user_id: int, task_data: Dict[str, Any]) -> None:
        """
        Set progress for a user's categorization task.

        Args:
            user_id: User ID
            task_data: Dictionary containing progress information
        """
        try:
            redis_client = get_redis_client()
            key = f"categorization_progress:{user_id}"
            redis_client.setex(key, 3600, json.dumps(task_data))  # Expire after 1 hour
        except Exception as e:
            api_logger.error(f"Failed to set progress for user {user_id}: {e}")

    @staticmethod
    def get_progress(user_id: int) -> Dict[str, Any] | None:
        """
        Get progress for a user's categorization task.

        Args:
            user_id: User ID

        Returns:
            Progress data or None if no active task
        """
        try:
            redis_client = get_redis_client()
            key = f"categorization_progress:{user_id}"
            data = redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            api_logger.error(f"Failed to get progress for user {user_id}: {e}")
            return None

    @staticmethod
    def clear_progress(user_id: int) -> None:
        """
        Clear progress for a user's categorization task.

        Args:
            user_id: User ID
        """
        try:
            redis_client = get_redis_client()
            key = f"categorization_progress:{user_id}"
            redis_client.delete(key)
        except Exception as e:
            api_logger.error(f"Failed to clear progress for user {user_id}: {e}")
