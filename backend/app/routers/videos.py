"""Videos router for managing YouTube videos."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, func, select
from datetime import datetime, timezone
import json
import asyncio
import uuid

from app.database import get_db
from app.dependencies import get_current_user, get_user_from_token
from app.models.user import User
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.schemas.video import (
    VideoResponse,
    PaginatedVideosResponse,
    CursorPaginatedVideosResponse,
    VideoCountResponse,
    BulkDeleteJobResponse,
    ClearCategorizationsResponse,
    BulkDeleteResult,
    BulkDeleteFailure,
    SemanticSearchResponse,
    SemanticSearchResult,
    EmbeddingStatsResponse,
    EmbeddingGenerateResponse,
)
from app.services.youtube_service import YouTubeService
from app.services.ai_service import AIService
from app.services.embedding_service import EmbeddingService
from app.logger import api_logger
from app.utils.qstash_client import trigger_categorization_job
from app.utils.cache_invalidation import invalidate_video_data
import math

router = APIRouter(prefix="/videos")


@router.get("/liked", response_model=CursorPaginatedVideosResponse)
async def get_liked_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = Query(None, description="Cursor for pagination (video_id)"),
    limit: int = Query(20, ge=1, le=100, description="Number of videos to fetch"),
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
    Get user's liked videos with cursor-based pagination.

    Supports:
    - Filtering by categories, tags, search query, categorization status
    - Sorting by liked_at, title, duration, published_at, view_count
    - Cursor-based pagination for efficient loading
    """
    # Build base query - only liked videos
    query = db.query(Video).filter(
        Video.user_id == current_user.id, Video.video_source == "liked"
    )

    # Apply filters using EXISTS subqueries to avoid duplicate counting
    if category_ids:
        from sqlalchemy import exists
        from app.models.video import video_categories

        cat_ids = [int(cid) for cid in category_ids.split(",")]
        category_subquery = exists().where(
            video_categories.c.video_id == Video.id,
            video_categories.c.category_id.in_(cat_ids),
        )
        query = query.filter(category_subquery)

    if tag_ids:
        from sqlalchemy import exists
        from app.models.video import video_tags

        t_ids = [int(tid) for tid in tag_ids.split(",")]
        tag_subquery = exists().where(
            video_tags.c.video_id == Video.id,
            video_tags.c.tag_id.in_(t_ids),
        )
        query = query.filter(tag_subquery)

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

    # Get total count before cursor filtering
    total_count = query.count()

    # Determine sort column
    sort_column = getattr(Video, sort_by, Video.liked_at)

    # Apply cursor filter if provided
    if cursor:
        try:
            cursor_id = int(cursor)
            # Get the cursor video to find its sort value
            cursor_video = (
                db.query(Video)
                .filter(Video.id == cursor_id, Video.user_id == current_user.id)
                .first()
            )
            if cursor_video:
                cursor_sort_value = getattr(
                    cursor_video, sort_by, cursor_video.liked_at
                )
                if cursor_sort_value is not None:
                    if sort_order == "desc":
                        # For descending: get items with smaller sort value OR same value but smaller id
                        query = query.filter(
                            or_(
                                sort_column < cursor_sort_value,
                                (sort_column == cursor_sort_value)
                                & (Video.id < cursor_id),
                            )
                        )
                    else:
                        # For ascending: get items with larger sort value OR same value but larger id
                        query = query.filter(
                            or_(
                                sort_column > cursor_sort_value,
                                (sort_column == cursor_sort_value)
                                & (Video.id > cursor_id),
                            )
                        )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor format"
            )

    # Apply sorting with secondary sort by id for stability
    if sort_order == "desc":
        query = query.order_by(sort_column.desc(), Video.id.desc())
    else:
        query = query.order_by(sort_column.asc(), Video.id.asc())

    # Fetch limit + 1 to check if there are more
    videos = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(videos) > limit
    if has_more:
        videos = videos[:limit]

    # Determine next cursor
    next_cursor = None
    if has_more and videos:
        next_cursor = str(videos[-1].id)

    return CursorPaginatedVideosResponse(
        videos=[VideoResponse.model_validate(v) for v in videos],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
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
        api_logger.error(
            f"Failed to sync videos for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync videos. Please try again later.",
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
        api_logger.error(
            f"Failed to categorize video {video_id} for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to categorize video. Please try again later.",
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
        items=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search_videos(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query for semantic search"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    similarity_threshold: float = Query(
        0.3, ge=0.0, le=1.0, description="Minimum similarity score (0-1)"
    ),
):
    """
    Semantic search across video content using AI embeddings.

    This uses OpenAI's text-embedding-3-small model to find videos that are
    semantically similar to your search query. Unlike keyword search, this
    understands meaning and context.

    Examples:
    - "cooking recipes" will find cooking videos even if they don't use those exact words
    - "learn programming" will find coding tutorials, software development content, etc.
    - "funny cat videos" will find humor/comedy content about cats

    Args:
        q: Search query text
        limit: Maximum number of results (1-100, default 20)
        similarity_threshold: Minimum similarity score to include (0-1, default 0.3)

    Returns:
        List of videos with similarity scores, ordered by relevance
    """
    try:
        embedding_service = EmbeddingService()
        results = await embedding_service.search_similar_videos(
            db=db,
            query=q,
            user_id=current_user.id,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )

        return SemanticSearchResponse(
            query=q,
            results=[SemanticSearchResult(**r) for r in results],
            total_results=len(results),
        )

    except Exception as e:
        api_logger.error(
            f"Semantic search failed for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic search failed. Please try again later.",
        )


@router.get("/embeddings/stats", response_model=EmbeddingStatsResponse)
async def get_embedding_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get statistics about video embeddings.

    Returns counts of total videos, videos with embeddings, and videos without.
    Use this to check if you need to generate embeddings before using semantic search.
    """
    embedding_service = EmbeddingService()
    stats = embedding_service.get_embedding_stats(db, current_user.id)

    percentage = (
        round((stats["embedded"] / stats["total"]) * 100, 2)
        if stats["total"] > 0
        else 0.0
    )

    return EmbeddingStatsResponse(
        total=stats["total"],
        embedded=stats["embedded"],
        not_embedded=stats["not_embedded"],
        percentage_embedded=percentage,
    )


# ============================================================================
# EMBEDDING GENERATION WITH SSE PROGRESS
# ============================================================================


def get_embedding_job_data(job_id: str) -> dict | None:
    """Get embedding job data from Redis."""
    redis_client = get_redis()
    data = redis_client.get(f"embedding_job:{job_id}")
    return json.loads(data) if data else None


def set_embedding_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set embedding job data in Redis with expiration (default 1 hour)."""
    redis_client = get_redis()
    redis_client.set(f"embedding_job:{job_id}", json.dumps(data), expire=expire)


@router.get("/embeddings/generate/stream")
async def stream_embedding_generation(
    token: str = Query(..., description="Authentication token"),
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to embed"
    ),
    batch_size: int = Query(
        50, ge=1, le=100, description="Videos per batch API call (50 recommended)"
    ),
    force_regenerate: bool = Query(
        False, description="Regenerate embeddings for all videos"
    ),
):
    """Generate embeddings with SSE progress using batch API calls (10-30x faster)."""
    from app.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()

    try:
        user = get_user_from_token(token, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        query = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .filter(Video.user_id == user.id)
        )

        if not force_regenerate:
            query = query.filter(Video.embedding.is_(None))

        query = query.order_by(Video.liked_at.desc())

        if max_videos:
            query = query.limit(max_videos)

        videos = query.all()
        total_count = len(videos)

        if total_count == 0:

            async def empty_generator():
                yield f"data: {json.dumps({'status': 'completed', 'total': 0, 'completed': 0, 'failed': 0, 'message': 'No videos to embed'})}\n\n"

            return StreamingResponse(
                empty_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        num_batches = (total_count + batch_size - 1) // batch_size

        async def event_generator():
            embedding_service = EmbeddingService()
            completed = 0
            failed = 0
            last_error: str | None = None

            yield f"data: {json.dumps({'status': 'running', 'total': total_count, 'completed': 0, 'failed': 0, 'current_batch': 0, 'total_batches': num_batches, 'batch_size': batch_size})}\n\n"

            for batch_idx in range(0, total_count, batch_size):
                batch = videos[batch_idx : batch_idx + batch_size]
                batch_num = batch_idx // batch_size + 1

                yield f"data: {json.dumps({'status': 'running', 'total': total_count, 'completed': completed, 'failed': failed, 'current_batch': batch_num, 'total_batches': num_batches, 'current_video': f'Batch {batch_num}/{num_batches} ({len(batch)} videos)'})}\n\n"

                try:
                    texts = [
                        embedding_service._build_embedding_text(video)
                        for video in batch
                    ]
                    embeddings = await embedding_service.generate_embeddings_batch(
                        texts
                    )

                    batch_success = 0
                    batch_failed = 0
                    for video, embedding in zip(batch, embeddings):
                        try:
                            embedding_str = (
                                embedding_service._format_embedding_for_pgvector(
                                    embedding
                                )
                            )
                            db.execute(
                                text(
                                    "UPDATE videos SET embedding = :embedding WHERE id = :id"
                                ),
                                {"embedding": embedding_str, "id": video.id},
                            )
                            batch_success += 1
                        except Exception as e:
                            api_logger.error(
                                f"Failed to update embedding for video {video.id}: {e}"
                            )
                            batch_failed += 1
                            last_error = str(e)

                    db.commit()
                    completed += batch_success
                    failed += batch_failed

                except Exception as e:
                    api_logger.error(f"Batch {batch_num} failed: {e}", exc_info=True)
                    failed += len(batch)
                    last_error = str(e)
                    try:
                        db.rollback()
                    except Exception:
                        pass

                progress_data = {
                    "status": "running",
                    "total": total_count,
                    "completed": completed,
                    "failed": failed,
                    "current_batch": batch_num,
                    "total_batches": num_batches,
                    "current_video": f"Completed batch {batch_num}/{num_batches}",
                }
                if last_error:
                    progress_data["last_error"] = last_error[:300]
                yield f"data: {json.dumps(progress_data)}\n\n"

            yield f"data: {json.dumps({'status': 'completed', 'total': total_count, 'completed': completed, 'failed': failed, 'current_batch': num_batches, 'total_batches': num_batches, 'current_video': None})}\n\n"

            api_logger.info(
                f"Batch embedding completed for user {user.id}: {completed} successful, {failed} failed in {num_batches} batches"
            )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start embedding generation",
        )
    finally:
        db.close()


@router.post("/embeddings/generate/start")
async def start_embedding_generation(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to embed (embeds all if not set)"
    ),
    batch_size: int = Query(
        50, ge=1, le=100, description="Videos per batch API call (50 recommended)"
    ),
    force_regenerate: bool = Query(
        False, description="Regenerate embeddings for all videos (including existing)"
    ),
):
    """Start batch embedding job and return job_id for progress tracking."""
    query = db.query(Video).filter(Video.user_id == current_user.id)

    if not force_regenerate:
        query = query.filter(Video.embedding.is_(None))

    query = query.order_by(Video.liked_at.desc())

    if max_videos:
        query = query.limit(max_videos)

    videos = query.all()
    total_count = len(videos)

    if total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No videos found for embedding generation",
        )

    video_ids = [video.id for video in videos]
    job_id = str(uuid.uuid4())
    num_batches = (total_count + batch_size - 1) // batch_size

    set_embedding_job_data(
        job_id,
        {
            "user_id": current_user.id,
            "total": total_count,
            "completed": 0,
            "failed": 0,
            "current_video": None,
            "status": "running",
            "batch_size": batch_size,
            "total_batches": num_batches,
        },
    )

    asyncio.create_task(run_embedding_generation(job_id, video_ids, batch_size))

    api_logger.info(
        f"Started batch embedding job {job_id} for {total_count} videos in {num_batches} batches (user {current_user.id})"
    )

    return {
        "job_id": job_id,
        "total_videos": total_count,
        "batch_size": batch_size,
        "total_batches": num_batches,
    }


@router.get("/embeddings/generate/stream/{job_id}")
async def stream_embedding_progress(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Stream real-time progress updates for embedding generation via SSE.
    """
    data = get_embedding_job_data(job_id)
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
        """Generate SSE events for embedding job progress."""
        try:
            while True:
                data = get_embedding_job_data(job_id)
                if not data:
                    break

                progress_data = {
                    "status": data.get("status", "running"),
                    "total": data.get("total", 0),
                    "completed": data.get("completed", 0),
                    "failed": data.get("failed", 0),
                    "current_video": data.get("current_video"),
                }

                if "error" in data:
                    progress_data["error"] = data["error"]

                yield f"data: {json.dumps(progress_data)}\n\n"

                # Stop streaming if job is complete or errored
                if data.get("status") in ["completed", "error"]:
                    break

                await asyncio.sleep(0.5)

        except Exception as e:
            api_logger.error(f"SSE stream error for embedding job {job_id}: {e}")
            error_data = {"status": "error", "error": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def run_embedding_generation(
    job_id: str,
    video_ids: list[int],
    batch_size: int,
):
    """Background task to generate embeddings with batch processing."""
    from app.database import SessionLocal
    from sqlalchemy import text

    api_logger.info(
        f"Starting batch embedding job {job_id} for {len(video_ids)} videos with batch_size={batch_size}"
    )

    db = SessionLocal()

    try:
        embedding_service = EmbeddingService()

        videos = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .filter(Video.id.in_(video_ids))
            .all()
        )
        video_map = {video.id: video for video in videos}

        num_batches = (len(video_ids) + batch_size - 1) // batch_size
        completed = 0
        failed = 0

        for batch_idx in range(0, len(video_ids), batch_size):
            batch_video_ids = video_ids[batch_idx : batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            batch_videos = [
                video_map[vid_id] for vid_id in batch_video_ids if vid_id in video_map
            ]

            if not batch_videos:
                continue

            data = get_embedding_job_data(job_id)
            if data:
                data["current_video"] = (
                    f"Batch {batch_num}/{num_batches} ({len(batch_videos)} videos)"
                )
                set_embedding_job_data(job_id, data)

            try:
                texts = [
                    embedding_service._build_embedding_text(video)
                    for video in batch_videos
                ]
                embeddings = await embedding_service.generate_embeddings_batch(texts)

                batch_success = 0
                batch_failed = 0
                for video, embedding in zip(batch_videos, embeddings):
                    try:
                        embedding_str = (
                            embedding_service._format_embedding_for_pgvector(embedding)
                        )
                        db.execute(
                            text(
                                "UPDATE videos SET embedding = :embedding WHERE id = :id"
                            ),
                            {"embedding": embedding_str, "id": video.id},
                        )
                        batch_success += 1
                    except Exception as e:
                        api_logger.error(
                            f"Failed to update embedding for video {video.id}: {e}"
                        )
                        batch_failed += 1

                db.commit()
                completed += batch_success
                failed += batch_failed

                data = get_embedding_job_data(job_id)
                if data:
                    data["completed"] = completed
                    data["failed"] = failed
                    data["current_video"] = f"Completed batch {batch_num}/{num_batches}"
                    set_embedding_job_data(job_id, data)

            except Exception as e:
                api_logger.error(
                    f"Job {job_id} batch {batch_num} failed: {e}", exc_info=True
                )
                failed += len(batch_videos)
                try:
                    db.rollback()
                except Exception:
                    pass

                data = get_embedding_job_data(job_id)
                if data:
                    data["failed"] = failed
                    data["last_error"] = str(e)[:300]
                    set_embedding_job_data(job_id, data)

        data = get_embedding_job_data(job_id)
        if data:
            data["status"] = "completed"
            data["completed"] = completed
            data["failed"] = failed
            data["current_video"] = None
            set_embedding_job_data(job_id, data, expire=7200)

        api_logger.info(
            f"Embedding job {job_id} completed: {completed} successful, {failed} failed in {num_batches} batches"
        )

    except Exception as e:
        data = get_embedding_job_data(job_id)
        if data:
            data["status"] = "error"
            data["error"] = str(e)
            set_embedding_job_data(job_id, data)
        api_logger.error(f"Embedding job {job_id} failed: {e}", exc_info=True)

    finally:
        db.close()


@router.post("/embeddings/generate", response_model=EmbeddingGenerateResponse)
async def generate_embeddings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_videos: int | None = Query(
        None, ge=1, description="Limit total videos to embed (embeds all if not set)"
    ),
    batch_size: int = Query(
        50, ge=1, le=100, description="Videos per batch API call (50 recommended)"
    ),
):
    """Generate embeddings synchronously using batch API calls (10-30x faster)."""
    try:
        query = (
            db.query(Video)
            .options(selectinload(Video.categories), selectinload(Video.tags))
            .filter(Video.user_id == current_user.id, Video.embedding.is_(None))
            .order_by(Video.liked_at.desc())
        )

        if max_videos:
            query = query.limit(max_videos)

        videos = query.all()

        if not videos:
            return EmbeddingGenerateResponse(
                success_count=0,
                failed_count=0,
                total=0,
                skipped=0,
                message="All videos already have embeddings",
            )

        api_logger.info(
            f"Batch embedding {len(videos)} videos (user {current_user.id}) with batch_size={batch_size}"
        )

        embedding_service = EmbeddingService()
        result = await embedding_service.embed_videos_batch_optimized(
            db=db,
            videos=videos,
            batch_size=batch_size,
        )

        return EmbeddingGenerateResponse(
            success_count=result["success_count"],
            failed_count=result["failed_count"],
            total=result["total"],
            skipped=result.get("skipped", 0),
            message=f"Generated embeddings for {result['success_count']} videos using batch API",
        )

    except Exception as e:
        api_logger.error(
            f"Embedding generation failed for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding generation failed. Please try again later.",
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

    # Count by video source
    liked_videos = (
        db.query(Video)
        .filter(Video.user_id == current_user.id, Video.video_source == "liked")
        .count()
    )

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
        "liked_videos": liked_videos,
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


@router.post("/clear-categorizations", response_model=ClearCategorizationsResponse)
async def clear_all_categorizations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Clear all category/tag associations for the current user's videos.

    Videos remain in the library. Only AI-generated categorization metadata is removed.
    """
    from app.models.category import video_categories
    from app.models.video import video_tags

    try:
        # Count impacted records before deletion for response payload.
        cleared_videos = (
            db.query(func.count(func.distinct(Video.id)))
            .outerjoin(video_categories, video_categories.c.video_id == Video.id)
            .outerjoin(video_tags, video_tags.c.video_id == Video.id)
            .filter(Video.user_id == current_user.id)
            .filter(
                or_(
                    Video.is_categorized.is_(True),
                    Video.categorized_at.isnot(None),
                    video_categories.c.video_id.isnot(None),
                    video_tags.c.video_id.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        removed_category_links = (
            db.query(func.count(video_categories.c.video_id))
            .join(Video, Video.id == video_categories.c.video_id)
            .filter(Video.user_id == current_user.id)
            .scalar()
            or 0
        )

        tag_usage_rows = (
            db.query(
                video_tags.c.tag_id,
                func.count(video_tags.c.video_id).label("link_count"),
            )
            .join(Video, Video.id == video_tags.c.video_id)
            .filter(Video.user_id == current_user.id)
            .group_by(video_tags.c.tag_id)
            .all()
        )
        removed_tag_links = sum(int(link_count) for _, link_count in tag_usage_rows)

        if (
            cleared_videos == 0
            and removed_category_links == 0
            and removed_tag_links == 0
        ):
            return ClearCategorizationsResponse(
                cleared_videos=0,
                removed_category_links=0,
                removed_tag_links=0,
                message="No categorizations found to clear",
            )

        # Keep global tag usage counts in sync with removed user associations.
        if tag_usage_rows:
            tag_ids = [tag_id for tag_id, _ in tag_usage_rows]
            decrement_by_tag = {
                tag_id: int(link_count) for tag_id, link_count in tag_usage_rows
            }
            tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            for tag in tags:
                tag.usage_count = max(
                    0, tag.usage_count - decrement_by_tag.get(tag.id, 0)
                )

        user_video_ids = select(Video.id).where(Video.user_id == current_user.id)

        db.execute(video_tags.delete().where(video_tags.c.video_id.in_(user_video_ids)))
        db.execute(
            video_categories.delete().where(
                video_categories.c.video_id.in_(user_video_ids)
            )
        )
        db.query(Video).filter(Video.user_id == current_user.id).update(
            {"is_categorized": False, "categorized_at": None},
            synchronize_session=False,
        )

        db.commit()
        invalidate_user_stats_cache(current_user.id)

        return ClearCategorizationsResponse(
            cleared_videos=int(cleared_videos),
            removed_category_links=int(removed_category_links),
            removed_tag_links=removed_tag_links,
            message="Cleared all categorizations and tags from your videos",
        )

    except Exception as e:
        db.rollback()
        api_logger.error(
            f"Failed to clear categorizations for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear categorizations. Please try again later.",
        )


@router.get("/count-by-tags", response_model=VideoCountResponse)
async def get_video_count_by_tags(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tag_ids: str = Query(..., description="Comma-separated tag IDs"),
):
    """
    Get count of videos matching specified tags.

    Used to show confirmation dialog before bulk delete.
    """
    from sqlalchemy import exists
    from app.models.video import video_tags

    t_ids = [int(tid) for tid in tag_ids.split(",")]

    # Build query with tag filter
    tag_subquery = exists().where(
        video_tags.c.video_id == Video.id,
        video_tags.c.tag_id.in_(t_ids),
    )

    count = (
        db.query(Video)
        .filter(Video.user_id == current_user.id)
        .filter(tag_subquery)
        .count()
    )

    return VideoCountResponse(count=count, tag_ids=t_ids)


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
        api_logger.error(
            f"Batch sync failed for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch sync videos. Please try again later.",
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

        if result["success_count"] > 0:
            invalidate_video_data(current_user.id)

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
        api_logger.error(
            f"Batch categorization failed for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch categorize videos. Please try again later.",
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
from app.redis_client import get_redis  # noqa: E402


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
    """Invalidate all video-derived caches for a user (delegating to centralized helper)."""
    invalidate_video_data(user_id)


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
            "status": "queued",  # Changed from "running" - job is queued for worker
            "paused": False,
            "results": [],
        },
    )

    # Trigger QStash job (or run locally if QStash not configured)
    try:
        qstash_result = await trigger_categorization_job(
            job_id=job_id,
            user_id=current_user.id,
            video_ids=video_ids,
            max_concurrent=max_concurrent,
        )

        # If running locally (dev mode), start background task
        if qstash_result.get("mode") == "local":
            asyncio.create_task(
                run_batch_categorization(
                    job_id, video_ids, max_concurrent, current_user.id
                )
            )
        else:
            api_logger.info(f"QStash job triggered: {qstash_result}")

    except Exception as e:
        api_logger.error(f"Failed to trigger QStash job: {e}", exc_info=True)
        # Fallback to local processing
        api_logger.info("Falling back to local background processing")
        asyncio.create_task(
            run_batch_categorization(job_id, video_ids, max_concurrent, current_user.id)
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
    try:
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
                api_logger.error(
                    f"SSE stream error for job {job_id}: {e}", exc_info=True
                )
                error_data = {"status": "error", "error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Failed to initialize SSE stream for job {job_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start progress stream. Please try again.",
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

    api_logger.info(
        f"Starting batch categorization job {job_id} with {len(video_ids)} videos, concurrency={max_concurrent}"
    )

    db = SessionLocal()

    try:
        ai_service = AIService()
        semaphore = asyncio.Semaphore(max_concurrent)

        # Fetch ALL videos upfront to avoid connection pool issues
        api_logger.info(f"Fetching all {len(video_ids)} videos from database...")
        all_videos = db.query(Video).filter(Video.id.in_(video_ids)).all()

        # Create a mapping of video_id -> video for quick lookup
        video_map = {video.id: video for video in all_videos}
        api_logger.info(f"Loaded {len(video_map)} videos into memory")

        # Process videos in batches of 10 for GPT batching efficiency
        batch_size = 10

        async def categorize_batch_with_progress(batch_video_ids: list[int]):
            """Categorize a batch of videos with a single API call."""
            async with semaphore:
                try:
                    # Check if job is paused/cancelled
                    data = get_job_data(job_id)
                    if not data:
                        api_logger.warning(f"Job {job_id} not found in Redis")
                        return

                    # Wait while paused
                    while data.get("paused", False):
                        await asyncio.sleep(1)
                        data = get_job_data(job_id)
                        if not data or data["status"] in [
                            "completed",
                            "error",
                            "cancelled",
                        ]:
                            return

                    # Get videos from the pre-loaded map
                    videos = [
                        video_map[vid_id]
                        for vid_id in batch_video_ids
                        if vid_id in video_map
                    ]
                    if not videos:
                        api_logger.error(
                            f"No videos found for batch: {batch_video_ids}"
                        )
                        return

                    api_logger.info(
                        f"Batch categorizing {len(videos)} videos with 1 API call"
                    )

                    # Update current video in Redis
                    data = get_job_data(job_id)
                    if data:
                        data["current_video"] = f"Batch of {len(videos)} videos"
                        set_job_data(job_id, data)

                    # Single API call for all videos in batch!
                    categorizations = await ai_service.categorize_videos_batch_async(
                        videos
                    )

                    # Apply categorizations to all videos
                    for video, categorization in zip(videos, categorizations):
                        try:
                            ai_service.apply_categorization(db, video, categorization)

                            # Update progress
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
                            api_logger.error(
                                f"Failed to apply categorization for video {video.id}: {e}"
                            )
                            data = get_job_data(job_id)
                            if data:
                                data["failed"] += 1
                                data["results"].append(
                                    {
                                        "video_id": video.id,
                                        "title": video.title,
                                        "success": False,
                                        "error": str(e),
                                    }
                                )
                                set_job_data(job_id, data)

                    api_logger.info(
                        f"Successfully categorized batch of {len(videos)} videos"
                    )

                except Exception as e:
                    api_logger.error(f"Failed to categorize batch: {e}", exc_info=True)
                    # Mark all videos in batch as failed
                    data = get_job_data(job_id)
                    if data:
                        for vid_id in batch_video_ids:
                            data["failed"] += 1
                            data["results"].append(
                                {
                                    "video_id": vid_id,
                                    "title": f"Video {vid_id}",
                                    "success": False,
                                    "error": str(e),
                                }
                            )
                        set_job_data(job_id, data)

        # Split videos into batches of 10
        video_batches = [
            video_ids[i : i + batch_size] for i in range(0, len(video_ids), batch_size)
        ]

        api_logger.info(
            f"Split {len(video_ids)} videos into {len(video_batches)} batches of ~{batch_size}"
        )

        # Run batch categorizations in parallel (max_concurrent batches at a time)
        tasks = [categorize_batch_with_progress(batch) for batch in video_batches]
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

        if result["success_count"] > 0:
            invalidate_video_data(user_id)

        api_logger.info(
            f"Background categorization complete for user {user_id}: "
            f"{result['success_count']} successful, {result['failed_count']} failed"
        )

    except Exception as e:
        api_logger.error(f"Background categorization failed for user {user_id}: {e}")
    finally:
        db.close()


# ============================================================================
# DELETE BY TAGS FUNCTIONALITY
# ============================================================================


def get_delete_job_data(job_id: str) -> dict | None:
    """Get delete job data from Redis."""
    redis_client = get_redis()
    data = redis_client.get(f"delete_job:{job_id}")
    return json.loads(data) if data else None


def set_delete_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set delete job data in Redis with expiration (default 1 hour)."""
    redis_client = get_redis()
    redis_client.set(f"delete_job:{job_id}", json.dumps(data), expire=expire)


@router.post("/delete-by-tags/start", response_model=BulkDeleteJobResponse)
async def start_bulk_delete_by_tags(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tag_ids: str = Query(..., description="Comma-separated tag IDs to filter videos"),
):
    """
    Start bulk delete operation for videos matching specified tags.

    Process:
    1. Finds all videos matching ANY of the specified tags
    2. Unlikes each video on YouTube (removes from liked videos)
    3. Hard deletes video from local database

    Returns job_id for progress tracking via SSE.

    Note: YouTube videos.rate API costs 50 quota units per call.
    With default 10,000 daily quota, max ~200 videos can be unliked per day.
    """
    from sqlalchemy import exists
    from app.models.video import video_tags

    t_ids = [int(tid) for tid in tag_ids.split(",")]

    # Build query with tag filter
    tag_subquery = exists().where(
        video_tags.c.video_id == Video.id,
        video_tags.c.tag_id.in_(t_ids),
    )

    videos = (
        db.query(Video)
        .filter(Video.user_id == current_user.id)
        .filter(tag_subquery)
        .all()
    )

    total_count = len(videos)

    if total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No videos found matching the specified tags",
        )

    # Extract video data (to avoid session detachment issues)
    video_data = [
        {"id": video.id, "youtube_id": video.youtube_id, "title": video.title}
        for video in videos
    ]

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Initialize job progress in Redis
    set_delete_job_data(
        job_id,
        {
            "user_id": current_user.id,
            "total": total_count,
            "unliked": 0,
            "deleted": 0,
            "failed": 0,
            "current_video": None,
            "status": "running",
            "error": None,
            "failures": [],
        },
    )

    # Start background task
    asyncio.create_task(run_bulk_delete(job_id, video_data, current_user.id))

    return BulkDeleteJobResponse(
        job_id=job_id,
        total_videos=total_count,
        message=f"Started bulk delete for {total_count} videos",
    )


@router.get("/delete-by-tags/stream/{job_id}")
async def stream_delete_progress(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Stream real-time progress updates for a delete job using Server-Sent Events.

    Args:
        job_id: The job ID returned from /delete-by-tags/start
        current_user: Authenticated user (validates ownership)

    Returns:
        StreamingResponse with real-time progress updates
    """
    data = get_delete_job_data(job_id)
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
        """Generate SSE events for delete job progress."""
        try:
            while True:
                data = get_delete_job_data(job_id)
                if not data:
                    break

                # Build progress data
                progress_data = {
                    "status": data.get("status", "running"),
                    "total": data.get("total", 0),
                    "unliked": data.get("unliked", 0),
                    "deleted": data.get("deleted", 0),
                    "failed": data.get("failed", 0),
                    "current_video": data.get("current_video"),
                    "failures": data.get("failures", []),
                }

                # Include error message if present
                if data.get("error"):
                    progress_data["error"] = data["error"]

                yield f"data: {json.dumps(progress_data)}\n\n"

                # Stop streaming if job is complete, cancelled, or errored
                if data.get("status") in ["completed", "error", "cancelled"]:
                    break

                await asyncio.sleep(0.5)  # Update every 500ms

        except Exception as e:
            api_logger.error(f"SSE stream error for delete job {job_id}: {e}")
            error_data = {"status": "error", "error": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/delete-by-tags/result/{job_id}", response_model=BulkDeleteResult)
async def get_delete_result(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the final result of a delete job.

    Args:
        job_id: The job ID returned from /delete-by-tags/start

    Returns:
        Final job result with success/failure details
    """
    data = get_delete_job_data(job_id)
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

    return BulkDeleteResult(
        status=data.get("status", "unknown"),
        total_videos=data.get("total", 0),
        unliked_count=data.get("unliked", 0),
        deleted_count=data.get("deleted", 0),
        failed_count=data.get("failed", 0),
        failures=[BulkDeleteFailure(**f) for f in data.get("failures", [])],
    )


@router.post("/delete-by-tags/cancel/{job_id}")
async def cancel_delete_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Cancel a running delete job.

    Note: Videos already deleted cannot be recovered.

    Args:
        job_id: The job ID to cancel
        current_user: Authenticated user (validates ownership)

    Returns:
        Confirmation message
    """
    data = get_delete_job_data(job_id)
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

    # Can only cancel running jobs
    if data["status"] != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {data['status']}",
        )

    # Mark job as cancelled
    data["status"] = "cancelled"
    data["current_video"] = None
    set_delete_job_data(job_id, data, expire=7200)  # Keep for 2 hours for review

    api_logger.info(f"Delete job {job_id} cancelled by user {current_user.id}")
    return {
        "message": "Job cancelled successfully",
        "job_id": job_id,
        "deleted_so_far": data.get("deleted", 0),
    }


async def run_bulk_delete(
    job_id: str,
    video_data: list[dict],
    user_id: int,
):
    """
    Background task to unlike videos on YouTube and delete from database.

    Args:
        job_id: Unique job identifier
        video_data: List of dicts with {id, youtube_id, title}
        user_id: User ID for database operations
    """
    from app.database import SessionLocal

    api_logger.info(f"Starting bulk delete job {job_id} with {len(video_data)} videos")

    db = SessionLocal()

    try:
        # Load user for YouTube service
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            data = get_delete_job_data(job_id)
            if data:
                data["status"] = "error"
                data["error"] = "User not found"
                set_delete_job_data(job_id, data)
            api_logger.error(f"User {user_id} not found for delete job {job_id}")
            return

        youtube_service = YouTubeService(user)

        # Update job status to running
        data = get_delete_job_data(job_id)
        if data:
            data["status"] = "running"
            set_delete_job_data(job_id, data)

        for video_info in video_data:
            # Check for cancellation
            data = get_delete_job_data(job_id)
            if not data or data.get("status") == "cancelled":
                api_logger.info(f"Delete job {job_id} was cancelled")
                break

            # Update current video
            data["current_video"] = video_info["title"][:50]
            set_delete_job_data(job_id, data)

            # Step 1: Unlike on YouTube
            unlike_result = youtube_service.unlike_video(video_info["youtube_id"])

            # Determine if we should proceed with DB delete
            should_delete = False
            if unlike_result["success"]:
                should_delete = True
                data["unliked"] += 1
            elif unlike_result.get("error_code") == 404:
                # Video doesn't exist on YouTube anymore - still delete from DB
                should_delete = True
                api_logger.info(
                    f"Video {video_info['youtube_id']} not found on YouTube, "
                    "proceeding with DB delete"
                )
            else:
                # YouTube API error - mark as failed
                data["failed"] += 1
                data["failures"].append(
                    {
                        "video_id": video_info["id"],
                        "youtube_id": video_info["youtube_id"],
                        "title": video_info["title"],
                        "error": unlike_result.get(
                            "error", "Failed to unlike on YouTube"
                        ),
                    }
                )
                api_logger.warning(
                    f"Failed to unlike video {video_info['youtube_id']}: "
                    f"{unlike_result.get('error')}"
                )

            # Step 2: Delete from database
            if should_delete:
                try:
                    video = db.query(Video).filter(Video.id == video_info["id"]).first()
                    if video:
                        # Update tag usage counts before deletion
                        for tag in video.tags:
                            tag.usage_count = max(0, tag.usage_count - 1)

                        db.delete(video)
                        db.commit()
                        data["deleted"] += 1
                        api_logger.debug(
                            f"Deleted video {video_info['id']} from database"
                        )
                except Exception as e:
                    api_logger.error(
                        f"Failed to delete video {video_info['id']} from DB: {e}"
                    )
                    data["failed"] += 1
                    data["failures"].append(
                        {
                            "video_id": video_info["id"],
                            "youtube_id": video_info["youtube_id"],
                            "title": video_info["title"],
                            "error": f"DB delete failed: {str(e)}",
                        }
                    )
                    db.rollback()

            set_delete_job_data(job_id, data)

        # Mark job as complete
        data = get_delete_job_data(job_id)
        if data and data["status"] != "cancelled":
            data["status"] = "completed"
            data["current_video"] = None
            set_delete_job_data(job_id, data, expire=7200)

        # Invalidate stats cache
        invalidate_user_stats_cache(user_id)

        api_logger.info(
            f"Delete job {job_id} completed: "
            f"{data['deleted'] if data else 0} deleted, "
            f"{data['failed'] if data else 0} failed"
        )

    except Exception as e:
        # Mark job as error
        data = get_delete_job_data(job_id)
        if data:
            data["status"] = "error"
            data["error"] = str(e)
            set_delete_job_data(job_id, data)
        api_logger.error(f"Delete job {job_id} failed: {e}", exc_info=True)

    finally:
        db.close()
