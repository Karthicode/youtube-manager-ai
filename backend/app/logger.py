"""Logging configuration for the application."""

import logging
import sys
from app.config import settings

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configure root logger
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],  # Vercel captures stdout
)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (use __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set level based on environment
    if settings.is_production:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    return logger


# Create loggers for different modules
app_logger = get_logger("app")
db_logger = get_logger("database")
redis_logger = get_logger("redis")
auth_logger = get_logger("auth")
api_logger = get_logger("api")
