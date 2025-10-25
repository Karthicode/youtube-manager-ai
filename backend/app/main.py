from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.logger import app_logger, db_logger, redis_logger
from app.routers import auth, videos, playlists, categories, tags, progress

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url=f"{settings.api_prefix}/docs" if not settings.is_production else None,
    redoc_url=f"{settings.api_prefix}/redoc" if not settings.is_production else None,
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# Configure CORS for local and production
# In production, only allow requests from configured frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Add trusted host middleware in production for additional security
if settings.is_production:
    # Extract hostnames from CORS origins for trusted hosts
    trusted_hosts = [
        origin.replace("https://", "").replace("http://", "")
        for origin in settings.cors_origins
    ]
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts + ["*.vercel.app"],
    )

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix, tags=["Authentication"])
app.include_router(videos.router, prefix=settings.api_prefix, tags=["Videos"])
app.include_router(playlists.router, prefix=settings.api_prefix, tags=["Playlists"])
app.include_router(categories.router, prefix=settings.api_prefix, tags=["Categories"])
app.include_router(tags.router, prefix=settings.api_prefix, tags=["Tags"])
app.include_router(progress.router, prefix=settings.api_prefix, tags=["Progress"])


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    app_logger.info(f"Starting {settings.app_name}")
    app_logger.info(f"Environment: {settings.environment}")
    app_logger.info(f"Debug mode: {settings.debug}")

    # Test database connection
    try:
        from app.database import engine

        with engine.connect():
            db_logger.info("Database connection successful")
    except Exception as e:
        db_logger.error(f"Database connection failed: {e}")

    # Test Redis connection
    try:
        from app.redis_client import redis_client

        if redis_client.client:
            redis_logger.info("Redis connection successful")
        else:
            redis_logger.warning("Redis not available (caching disabled)")
    except Exception as e:
        redis_logger.error(f"Redis connection failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    app_logger.info("Shutting down application")

    # Close Redis connection
    try:
        from app.redis_client import redis_client

        redis_client.close()
        redis_logger.info("Redis connection closed")
    except Exception as e:
        redis_logger.warning(f"Error closing Redis connection: {e}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    # Test database
    db_status = "connected"
    try:
        from app.database import engine

        with engine.connect():
            pass
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Test Redis
    redis_status = "connected"
    try:
        from app.redis_client import redis_client

        if not redis_client.client or not redis_client.client.ping():
            redis_status = "disconnected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.environment,
        "database": db_status,
        "redis": redis_status,
    }
