from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, videos, playlists, categories, tags

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix, tags=["Authentication"])
app.include_router(videos.router, prefix=settings.api_prefix, tags=["Videos"])
app.include_router(playlists.router, prefix=settings.api_prefix, tags=["Playlists"])
app.include_router(categories.router, prefix=settings.api_prefix, tags=["Categories"])
app.include_router(tags.router, prefix=settings.api_prefix, tags=["Tags"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }
