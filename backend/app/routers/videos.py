"""Videos router for managing YouTube videos."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime, timezone
import json
import asyncio
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.schemas.video import VideoResponse, PaginatedVideosResponse
from app.services.youtube_service import YouTubeService
from app.services.ai_service import AIService
from app.logger import api_logger
import math

router = APIRouter(prefix="/videos")


@router.get("/liked", response_model=PaginatedVideosResponse)
async def get_liked_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_ids: str | None = Query(None, description="Comma-separated category IDs"),
    tag_ids: str | None = Query(None, description="Comma-separated tag IDs"),
    search: str | None = Query(None, description="Search in title and description"),
    is_categorized: bool | None = Query(
        None, description="Filter by categorization status"
    ),
    sort_by: str = Query("liked_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
):
    """
    Get user's liked videos with filtering, sorting, and pagination.

    Supports:
    - Filtering by categories, tags, search query, categorization status
    - Sorting by liked_at, title, duration, published_at, view_count
    - Pagination with total count
    """
    # Build base query
    query = db.query(Video).filter(Video.user_id == current_user.id)

    # Apply filters
    if category_ids:
        cat_ids = [int(cid) for cid in category_ids.split(",")]
        query = query.join(Video.categories).filter(Category.id.in_(cat_ids))

    if tag_ids:
        t_ids = [int(tid) for tid in tag_ids.split(",")]
        query = query.join(Video.tags).filter(Tag.id.in_(t_ids))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Video.title.ilike(search_term),
                Video.description.ilike(search_term),
                Video.channel_title.ilike(search_term),
            )
        )

    if is_categorized is not None:
        query = query.filter(Video.is_categorized == is_categorized)

    # Get total count before pagination
    total = query.count()

    # Apply sorting
    sort_column = getattr(Video, sort_by, Video.liked_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    videos = query.offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedVideosResponse(
        items=videos,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/sync")
async def sync_liked_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_results: int = Query(20, ge=1, le=50),
):
    """
    Sync latest liked videos from YouTube (only fetches new/recent videos).

    Args:
        max_results: Maximum number of recent videos to fetch (1-50, default 20)

    Note: This only syncs videos, does not categorize.
          Use /categorize-batch to categorize uncategorized videos.
    """
    try:
        # Fetch videos from YouTube
        youtube_service = YouTubeService(current_user)
        videos, count = youtube_service.fetch_liked_videos(db, max_results=max_results)

        # Update user's last sync time
        from datetime import datetime, timezone

        current_user.last_sync_at = datetime.now(timezone.utc)
        db.commit()

        # Invalidate stats cache since videos were synced
        if count > 0:
            invalidate_user_stats_cache(current_user.id)

        return {
            "status": "success",
            "videos_synced": count,
            "total_videos": len(videos),
            "message": f"Synced {count} latest videos from YouTube",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync videos: {str(e)}",
        )


@router.post("/{video_id}/categorize", response_model=VideoResponse)
async def categorize_video(
    video_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Re-categorize a specific video using AI.

    Useful for re-running categorization or correcting AI mistakes.
    """
    # Get video
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.user_id == current_user.id)
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Categorize with AI
    try:
        ai_service = AIService()
        categorization = ai_service.categorize_video(db, video)
        updated_video = ai_service.apply_categorization(db, video, categorization)

        # Invalidate stats cache since video was categorized
        invalidate_user_stats_cache(current_user.id)

        return updated_video

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to categorize video: {str(e)}",
        )


@router.get("/search", response_model=PaginatedVideosResponse)
async def search_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Full-text search across video titles, descriptions, and channels.

    Args:
        q: Search query string
        page: Page number
        page_size: Results per page
    """
    search_term = f"%{q}%"

    query = (
        db.query(Video)
        .filter(Video.user_id == current_user.id)
        .filter(
            or_(
                Video.title.ilike(search_term),
                Video.description.ilike(search_term),
                Video.channel_title.ilike(search_term),
            )
        )
        .order_by(Video.liked_at.desc())
    )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    videos = query.offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedVideosResponse(
        items=videos,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/stats")
async def get_video_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get statistics about user's videos (cached for 5 minutes).

    Returns counts, categorization status, top categories, etc.

    Args:
        force_refresh: Skip cache and fetch fresh data from database
    """
    # Try to get from cache first
    if not force_refresh:
        cached_stats = get_cached_stats(current_user.id)
        if cached_stats:
            api_logger.debug(f"Returning cached stats for user {current_user.id}")
            return cached_stats

    # Cache miss or force refresh - query database
    api_logger.info(f"Fetching fresh stats for user {current_user.id}")

    total_videos = db.query(Video).filter(Video.user_id == current_user.id).count()

    categorized = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, Video.is_categorized)
        .count()
    )

    uncategorized = total_videos - categorized

    # Top categories
    top_categories = (
        db.query(Category.name, func.count(Video.id).label("count"))
        .join(Video.categories)
        .filter(Video.user_id == current_user.id)
        .group_by(Category.id, Category.name)
        .order_by(func.count(Video.id).desc())
        .limit(10)
        .all()
    )

    # Top tags
    top_tags = (
        db.query(Tag.name, func.count(Video.id).label("count"))
        .join(Video.tags)
        .filter(Video.user_id == current_user.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(Video.id).desc())
        .limit(10)
        .all()
    )

    stats = {
        "total_videos": total_videos,
        "categorized": categorized,
        "uncategorized": uncategorized,
        "categorization_percentage": (
            round((categorized / total_videos) * 100, 2) if total_videos > 0 else 0
        ),
        "top_categories": [
            {"name": name, "count": count} for name, count in top_categories
        ],
        "top_tags": [{"name": name, "count": count} for name, count in top_tags],
    }

    # Cache the results for 5 minutes
    set_cached_stats(current_user.id, stats, expire=300)

    return stats


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get a specific video by ID."""
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.user_id == current_user.id)
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    return video


@router.post("/sync/batch")
async def sync_all_liked_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    auto_categorize: bool = Query(
        False, description="Automatically categorize new videos (slower)"
    ),
):
    """
    Sync ALL liked videos from YouTube without limit using pagination.

    This will fetch all your liked videos by making multiple requests to YouTube API.
    Can take several minutes for large libraries (1000+ videos).

    Args:
        auto_categorize: Whether to categorize new videos immediately (not recommended for large batches)
    """
    try:
        youtube_service = YouTubeService(current_user)
        all_videos = []
        total_synced = 0
        page_token = None
        page_num = 1

        api_logger.info(f"Starting batch sync for user {current_user.id}")

        # Fetch all pages
        while True:
            api_logger.info(f"Fetching page {page_num}...")

            # Fetch 50 videos per page (max allowed by YouTube API)
            videos, next_page_token = youtube_service.fetch_liked_videos_paginated(
                db, page_token=page_token, max_results=50
            )

            all_videos.extend(videos)
            total_synced += len(videos)

            api_logger.info(
                f"Page {page_num}: Fetched {len(videos)} videos (Total: {total_synced})"
            )

            # Check if there are more pages
            if not next_page_token:
                api_logger.info(f"Reached end of liked videos. Total: {total_synced}")
                break

            page_token = next_page_token
            page_num += 1

            # Safety limit to prevent infinite loops
            if page_num > 100:  # 100 pages * 50 = 5000 videos max
                api_logger.warning("Reached safety limit of 100 pages")
                break

        # Update user's last sync time
        current_user.last_sync_at = datetime.now(timezone.utc)
        db.commit()

        # Categorize if requested
        categorized_count = 0
        if auto_categorize and all_videos:
            api_logger.info(f"Starting categorization of {len(all_videos)} videos...")
            ai_service = AIService()
            uncategorized = [v for v in all_videos if not v.is_categorized]

            for i, video in enumerate(uncategorized, 1):
                try:
                    api_logger.info(
                        f"Categorizing {i}/{len(uncategorized)}: {video.title[:50]}..."
                    )
                    categorization = ai_service.categorize_video(db, video)
                    ai_service.apply_categorization(db, video, categorization)
                    categorized_count += 1
                except Exception as e:
                    api_logger.error(f"Failed to categorize video {video.id}: {e}")

        # Invalidate stats cache since videos were synced/categorized
        if total_synced > 0 or categorized_count > 0:
            invalidate_user_stats_cache(current_user.id)

        return {
            "status": "success",
            "total_videos_synced": total_synced,
            "videos_categorized": categorized_count,
            "pages_fetched": page_num,
            "message": f"Successfully synced {total_synced} videos",
        }

    except Exception as e:
        api_logger.error(f"Batch sync failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch sync videos: {str(e)}",
        )


@router.post("/categorize-batch")
async def categorize_all_uncategorized(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_concurrent: int = Query(
        10,
        ge=1,
        le=50,
        description="Maximum concurrent API calls (higher = faster but more API usage)",
    ),
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to categorize"
    ),
):
    """
    Categorize all uncategorized videos in parallel using AsyncOpenAI.

    This uses true async I/O for maximum performance, processing multiple
    videos concurrently. Much faster than the old ThreadPoolExecutor approach.

    Args:
        max_concurrent: Maximum concurrent OpenAI API calls (1-50, default 10)
        max_videos: Optional limit on total videos to categorize

    Performance:
        - 10 concurrent requests: ~10x faster than sequential
        - 20 concurrent requests: ~15x faster (diminishing returns)
        - Limited by OpenAI rate limits (adjust max_concurrent if you hit limits)
    """
    try:
        # Get all uncategorized videos
        query = (
            db.query(Video)
            .filter(Video.user_id == current_user.id, ~Video.is_categorized)
            .order_by(Video.liked_at.desc())
        )

        if max_videos:
            query = query.limit(max_videos)

        uncategorized_videos = query.all()
        total_count = len(uncategorized_videos)

        if total_count == 0:
            return {
                "status": "success",
                "message": "No uncategorized videos found",
                "total_categorized": 0,
                "total_failed": 0,
            }

        api_logger.info(
            f"Starting async parallel categorization of {total_count} videos with max_concurrent={max_concurrent}"
        )

        # Use new async batch categorization with progress tracking
        ai_service = AIService()
        result = await ai_service.batch_categorize_videos_async(
            db,
            uncategorized_videos,
            max_concurrent=max_concurrent,
            user_id=current_user.id,
        )

        categorized_count = result["success_count"]
        failed_count = result["failed_count"]

        return {
            "status": "success",
            "total_videos": total_count,
            "total_categorized": categorized_count,
            "total_failed": failed_count,
            "success_rate": (
                round((categorized_count / total_count) * 100, 2)
                if total_count > 0
                else 0
            ),
            "message": f"Categorized {categorized_count} out of {total_count} videos using parallel async processing",
            "details": result.get("results", []),
        }

    except Exception as e:
        api_logger.error(f"Batch categorization failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch categorize: {str(e)}",
        )


@router.post("/categorize-batch/background")
async def categorize_in_background(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    max_concurrent: int = Query(
        10, ge=1, le=50, description="Maximum concurrent API calls"
    ),
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to categorize"
    ),
):
    """
    Start categorizing videos in the background (non-blocking).

    This endpoint returns immediately and processes videos in the background.
    Useful for large batches where you don't want to wait for completion.

    The categorization will continue even after the API returns a response.
    Check Vercel logs or query your videos to see when categorization completes.

    Args:
        max_concurrent: Maximum concurrent OpenAI API calls (1-50, default 10)
        max_videos: Optional limit on total videos to categorize

    Returns:
        Immediate response with count of videos to be categorized
    """
    # Get count of uncategorized videos
    query = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, ~Video.is_categorized)
        .order_by(Video.liked_at.desc())
    )

    if max_videos:
        query = query.limit(max_videos)

    total_count = query.count()

    if total_count == 0:
        return {
            "status": "success",
            "message": "No uncategorized videos found",
            "total_to_categorize": 0,
        }

    # Add background task
    background_tasks.add_task(
        background_categorize_videos,
        user_id=current_user.id,
        max_concurrent=max_concurrent,
        max_videos=max_videos,
    )

    api_logger.info(
        f"Queued background categorization for {total_count} videos (user {current_user.id})"
    )

    return {
        "status": "started",
        "message": f"Categorization started in background for {total_count} videos",
        "total_to_categorize": total_count,
        "max_concurrent": max_concurrent,
        "note": "Check Vercel logs or query your videos to see when categorization completes",
    }


# Redis-based job progress store for persistence and multi-instance scaling
from app.redis_client import get_redis


def get_job_data(job_id: str) -> dict | None:
    """Get job data from Redis."""
    redis_client = get_redis()
    data = redis_client.get(f"categorization_job:{job_id}")
    return json.loads(data) if data else None


def set_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set job data in Redis with expiration (default 1 hour)."""
    redis_client = get_redis()
    redis_client.set(f"categorization_job:{job_id}", json.dumps(data), expire=expire)


def delete_job_data(job_id: str) -> None:
    """Delete job data from Redis."""
    redis_client = get_redis()
    redis_client.delete(f"categorization_job:{job_id}")


def get_cached_stats(user_id: int) -> dict | None:
    """Get cached stats from Redis."""
    redis_client = get_redis()
    data = redis_client.get(f"user_stats:{user_id}")
    return json.loads(data) if data else None


def set_cached_stats(user_id: int, stats: dict, expire: int = 300) -> None:
    """Set cached stats in Redis with expiration (default 5 minutes)."""
    redis_client = get_redis()
    redis_client.set(f"user_stats:{user_id}", json.dumps(stats), expire=expire)


def invalidate_user_stats_cache(user_id: int) -> None:
    """Invalidate cached stats for a user."""
    redis_client = get_redis()
    redis_client.delete(f"user_stats:{user_id}")


@router.post("/categorize-batch/start")
async def start_batch_categorization(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_concurrent: int = Query(
        10, ge=1, le=50, description="Maximum concurrent API calls"
    ),
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to categorize"
    ),
):
    """
    Start batch categorization job and return a job_id for progress tracking.

    This endpoint immediately returns a job_id that can be used to stream progress
    via the /categorize-batch/stream/{job_id} endpoint.

    Args:
        max_concurrent: Maximum concurrent OpenAI API calls (1-50, default 10)
        max_videos: Optional limit on total videos to categorize

    Returns:
        job_id: Unique identifier for tracking this categorization job
    """
    # Get uncategorized videos
    query = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, ~Video.is_categorized)
        .order_by(Video.liked_at.desc())
    )

    if max_videos:
        query = query.limit(max_videos)

    uncategorized_videos = query.all()
    total_count = len(uncategorized_videos)

    if total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uncategorized videos found",
        )

    # Extract video IDs (to avoid session detachment issues)
    video_ids = [video.id for video in uncategorized_videos]

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Initialize job progress in Redis
    set_job_data(
        job_id,
        {
            "user_id": current_user.id,
            "total": total_count,
            "completed": 0,
            "failed": 0,
            "current_video": None,
            "status": "running",
            "paused": False,
            "results": [],
        },
    )

    # Start categorization in background (pass video IDs, not ORM objects)
    asyncio.create_task(
        run_batch_categorization(
            job_id, video_ids, max_concurrent, current_user.id
        )
    )

    return {"job_id": job_id, "total_videos": total_count}


@router.get("/categorize-batch/stream/{job_id}")
async def stream_categorization_progress(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Stream real-time progress updates for a categorization job using Server-Sent Events.

    Args:
        job_id: The job ID returned from /categorize-batch/start
        current_user: Authenticated user (validates ownership)

    Returns:
        StreamingResponse with real-time progress updates
    """
    data = get_job_data(job_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Verify job belongs to current user
    if data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job",
        )

    async def event_generator():
        """Generate SSE events for job progress."""
        try:
            while True:
                data = get_job_data(job_id)
                if not data:
                    break

                # Ensure all required fields exist
                progress_data = {
                    "status": data.get("status", "running"),
                    "total": data.get("total", 0),
                    "completed": data.get("completed", 0),
                    "failed": data.get("failed", 0),
                    "current_video": data.get("current_video"),
                    "paused": data.get("paused", False),
                }

                # Include error message if present
                if "error" in data:
                    progress_data["error"] = data["error"]

                yield f"data: {json.dumps(progress_data)}\n\n"

                # Stop streaming if job is complete, cancelled, or errored
                if data.get("status") in ["completed", "error", "cancelled"]:
                    break

                await asyncio.sleep(0.5)  # Update every 500ms

        except Exception as e:
            api_logger.error(f"SSE stream error for job {job_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({{'status': 'error', 'error': str(e)}})}\\n\\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/categorize-batch/result/{job_id}")
async def get_categorization_result(job_id: str):
    """
    Get the final result of a categorization job.

    Args:
        job_id: The job ID returned from /categorize-batch/start

    Returns:
        Final job result with all categorized videos
    """
    data = get_job_data(job_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    return data


@router.post("/categorize-batch/pause/{job_id}")
async def pause_categorization_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Pause a running categorization job.

    Args:
        job_id: The job ID to pause
        current_user: Authenticated user (validates ownership)

    Returns:
        Updated job data with paused status
    """
    data = get_job_data(job_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Verify job belongs to current user
    if data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job",
        )

    # Can only pause running jobs
    if data["status"] != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause job with status: {data['status']}",
        )

    # Update pause state
    data["paused"] = True
    data["status"] = "paused"
    set_job_data(job_id, data)

    api_logger.info(f"Job {job_id} paused by user {current_user.id}")
    return {"message": "Job paused successfully", "job_id": job_id}


@router.post("/categorize-batch/resume/{job_id}")
async def resume_categorization_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Resume a paused categorization job.

    Args:
        job_id: The job ID to resume
        current_user: Authenticated user (validates ownership)

    Returns:
        Updated job data with running status
    """
    data = get_job_data(job_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Verify job belongs to current user
    if data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job",
        )

    # Can only resume paused jobs
    if data["status"] != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume job with status: {data['status']}",
        )

    # Update pause state
    data["paused"] = False
    data["status"] = "running"
    set_job_data(job_id, data)

    api_logger.info(f"Job {job_id} resumed by user {current_user.id}")
    return {"message": "Job resumed successfully", "job_id": job_id}


@router.post("/categorize-batch/cancel/{job_id}")
async def cancel_categorization_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Cancel a running or paused categorization job.

    Args:
        job_id: The job ID to cancel
        current_user: Authenticated user (validates ownership)

    Returns:
        Confirmation message
    """
    data = get_job_data(job_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Verify job belongs to current user
    if data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job",
        )

    # Can only cancel running or paused jobs
    if data["status"] not in ["running", "paused"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {data['status']}",
        )

    # Mark job as cancelled
    data["status"] = "cancelled"
    data["paused"] = False
    data["current_video"] = None
    set_job_data(job_id, data, expire=7200)  # Keep for 2 hours for review

    api_logger.info(f"Job {job_id} cancelled by user {current_user.id}")
    return {"message": "Job cancelled successfully", "job_id": job_id}


async def run_batch_categorization(
    job_id: str, video_ids: list[int], max_concurrent: int, user_id: int
):
    """
    Background task to categorize videos and update job progress.

    Args:
        job_id: Unique job identifier
        video_ids: List of video IDs to categorize
        max_concurrent: Maximum concurrent API calls
        user_id: User ID for database operations
    """
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        ai_service = AIService()
        semaphore = asyncio.Semaphore(max_concurrent)

        async def categorize_with_progress(video_id: int):
            """Categorize a single video and update progress."""
            async with semaphore:
                # Create a new session for this task to avoid detachment issues
                task_db = SessionLocal()
                try:
                    # Check if job is paused before processing
                    data = get_job_data(job_id)
                    if not data:
                        return  # Job deleted

                    # Wait while paused
                    while data.get("paused", False):
                        await asyncio.sleep(1)  # Check every second
                        data = get_job_data(job_id)
                        if not data or data["status"] in ["completed", "error", "cancelled"]:
                            return  # Job deleted, stopped, or cancelled

                    # Fetch video fresh from database with this task's session
                    video = task_db.query(Video).filter(Video.id == video_id).first()
                    if not video:
                        api_logger.error(f"Video {video_id} not found")
                        return

                    # Update current video in Redis
                    data["current_video"] = video.title[:50]
                    set_job_data(job_id, data)

                    categorization = await ai_service.categorize_video_async(video)
                    ai_service.apply_categorization(task_db, video, categorization)

                    # Update progress in Redis
                    data = get_job_data(job_id)
                    if data:
                        data["completed"] += 1
                        data["results"].append(
                            {
                                "video_id": video.id,
                                "title": video.title,
                                "success": True,
                                "categories": categorization.primary_categories
                                + categorization.secondary_categories,
                                "tags": categorization.tags,
                            }
                        )
                        set_job_data(job_id, data)

                except Exception as e:
                    # Update failure count in Redis
                    data = get_job_data(job_id)
                    if data:
                        data["failed"] += 1
                        data["results"].append(
                            {
                                "video_id": video_id,
                                "title": video.title if video else f"Video {video_id}",
                                "success": False,
                                "error": str(e),
                            }
                        )
                        set_job_data(job_id, data)
                    api_logger.error(f"Failed to categorize video {video_id}: {e}")
                finally:
                    # Always close the task's database session
                    task_db.close()

        # Run all categorizations in parallel
        tasks = [categorize_with_progress(video_id) for video_id in video_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Mark job as complete in Redis
        data = get_job_data(job_id)
        if data:
            data["status"] = "completed"
            data["current_video"] = None
            set_job_data(job_id, data, expire=7200)  # Keep result for 2 hours

        # Invalidate stats cache since videos were categorized
        invalidate_user_stats_cache(user_id)

        api_logger.info(
            f"Job {job_id} completed: {data['completed'] if data else 0} successful, "
            f"{data['failed'] if data else 0} failed"
        )

    except Exception as e:
        # Mark job as error in Redis
        data = get_job_data(job_id)
        if data:
            data["status"] = "error"
            data["error"] = str(e)
            set_job_data(job_id, data)
        api_logger.error(f"Job {job_id} failed: {e}")

    finally:
        db.close()


async def background_categorize_videos(
    user_id: int, max_concurrent: int = 10, max_videos: int | None = None
):
    """
    Background task to categorize videos asynchronously.

    This runs in the background without blocking the API response.

    Args:
        user_id: User ID to categorize videos for
        max_concurrent: Maximum concurrent API calls
        max_videos: Optional limit on total videos to categorize
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        api_logger.info(
            f"Background categorization started for user {user_id} with max_concurrent={max_concurrent}"
        )

        # Get uncategorized videos
        query = (
            db.query(Video)
            .filter(Video.user_id == user_id, ~Video.is_categorized)
            .order_by(Video.liked_at.desc())
        )

        if max_videos:
            query = query.limit(max_videos)

        uncategorized_videos = query.all()

        if not uncategorized_videos:
            api_logger.info(f"No uncategorized videos found for user {user_id}")
            return

        # Run async categorization with progress tracking
        ai_service = AIService()
        result = await ai_service.batch_categorize_videos_async(
            db, uncategorized_videos, max_concurrent=max_concurrent, user_id=user_id
        )

        api_logger.info(
            f"Background categorization complete for user {user_id}: "
            f"{result['success_count']} successful, {result['failed_count']} failed"
        )

    except Exception as e:
        api_logger.error(f"Background categorization failed for user {user_id}: {e}")
    finally:
        db.close()
