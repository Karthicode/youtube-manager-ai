"""Redis client for caching with support for local and Upstash Redis."""

import redis
from redis.exceptions import RedisError
from app.config import settings
from app.logger import redis_logger


class RedisClient:
    """Redis client wrapper supporting both local and Upstash Redis."""

    def __init__(self):
        """Initialize Redis client based on environment."""
        self._client = None
        self._connect()

    def _connect(self):
        """Connect to Redis (local or Upstash)."""
        try:
            # Parse Redis URL and create client
            # Both local (redis://) and Upstash (rediss://) are supported
            self._client = redis.from_url(
                settings.redis_url,
                decode_responses=True,  # Decode bytes to strings
                socket_connect_timeout=5,  # Connection timeout
                socket_timeout=5,  # Operation timeout
                retry_on_timeout=True,
                health_check_interval=30,  # Health check every 30s
            )

            # Test connection
            self._client.ping()
            redis_logger.info(f"Redis connected successfully ({settings.environment})")

        except RedisError as e:
            redis_logger.error(f"Redis connection failed: {e}")
            redis_logger.warning("Application will continue without caching")
            self._client = None

    @property
    def client(self):
        """Get Redis client instance."""
        return self._client

    def get(self, key: str) -> str | None:
        """Get value from Redis."""
        if not self._client:
            return None

        try:
            return self._client.get(key)
        except RedisError as e:
            redis_logger.debug(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: str, expire: int | None = None) -> bool:
        """
        Set value in Redis.

        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            if expire:
                return self._client.setex(key, expire, value)
            else:
                return self._client.set(key, value)
        except RedisError as e:
            redis_logger.debug(f"Redis SET error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self._client:
            return False

        try:
            return self._client.delete(key) > 0
        except RedisError as e:
            redis_logger.debug(f"Redis DELETE error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self._client:
            return False

        try:
            return self._client.exists(key) > 0
        except RedisError as e:
            redis_logger.debug(f"Redis EXISTS error: {e}")
            return False

    def flush_all(self) -> bool:
        """Flush all keys (use with caution!)."""
        if not self._client:
            return False

        try:
            self._client.flushall()
            redis_logger.warning("Redis FLUSHALL executed - all keys deleted")
            return True
        except RedisError as e:
            redis_logger.error(f"Redis FLUSHALL error: {e}")
            return False

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()


# Global Redis client instance
redis_client = RedisClient()


def get_redis():
    """Dependency for getting Redis client."""
    return redis_client
