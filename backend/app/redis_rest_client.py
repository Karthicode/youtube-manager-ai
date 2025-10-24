"""Redis REST client for serverless environments (Upstash)."""

import os
import requests
from typing import Optional
from app.config import settings
from app.logger import redis_logger


class RedisRestClient:
    """
    Redis client using Upstash REST API.

    Better for serverless environments (Vercel) as it doesn't maintain connections.
    Falls back to regular Redis client if REST credentials not available.
    """

    def __init__(self):
        """Initialize REST client with Upstash credentials."""
        self._rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
        self._rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self._available = bool(self._rest_url and self._rest_token)

        if self._available:
            redis_logger.info("Redis REST client initialized (Upstash)")
        else:
            redis_logger.info("Redis REST credentials not found, using standard Redis")

    @property
    def is_available(self) -> bool:
        """Check if REST client is available."""
        return self._available

    def _request(self, *args) -> dict:
        """
        Execute Redis command via REST API.

        Args:
            *args: Redis command and arguments

        Returns:
            Response dict with 'result' key
        """
        if not self._available:
            return {"result": None}

        url = f"{self._rest_url}/{'/'.join(str(arg) for arg in args)}"
        headers = {"Authorization": f"Bearer {self._rest_token}"}

        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            redis_logger.debug(f"Redis REST error: {e}")
            return {"result": None}

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        result = self._request("get", key)
        return result.get("result")

    def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """
        Set value in Redis.

        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        if expire:
            result = self._request("setex", key, expire, value)
        else:
            result = self._request("set", key, value)

        return result.get("result") == "OK"

    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        result = self._request("del", key)
        return result.get("result", 0) > 0

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        result = self._request("exists", key)
        return result.get("result", 0) > 0

    def flush_all(self) -> bool:
        """Flush all keys (use with caution!)."""
        result = self._request("flushall")
        return result.get("result") == "OK"


# Create smart client that uses REST if available, otherwise falls back to regular Redis
def get_redis_client():
    """Get appropriate Redis client based on environment."""
    rest_client = RedisRestClient()

    if rest_client.is_available and settings.is_production:
        # Use REST API in production (better for serverless)
        return rest_client
    else:
        # Use regular Redis client for local development
        from app.redis_client import redis_client

        return redis_client


# Global instance
redis_client = get_redis_client()


def get_redis():
    """Dependency for getting Redis client."""
    return redis_client
