"""Playlists router for managing YouTube playlists."""

from __future__ import annotations

from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.playlist import Playlist
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.schemas.playlist import (
    PlaylistResponse,
    PlaylistWithVideos,
    CreatePlaylistFromFiltersRequest,
    CreatePlaylistFromFiltersResponse,
    PlaylistVideosCursorResponse,
    SmartPlaylistRequest,
    PlaylistSuggestion,
    SmartPlaylistConfirmRequest,
)
from app.services.youtube_service import YouTubeService
from app.services.ai_service import AIService
from app.logger import api_logger
from app.utils.qstash_client import trigger_playlist_video_addition_job
from app.redis_client import get_redis

router = APIRouter(prefix="/playlists")


@router.get("/", response_model=List[PlaylistResponse])
async def get_playlists(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search in playlist title"),
):
    """
    Get user's playlists with optional search and pagination.

    Args:
        page: Page number (starts at 1)
        page_size: Number of results per page (1-100)
        search: Optional search query for playlist titles
    """
    query = db.query(Playlist).filter(
        Playlist.user_id == current_user.id,
        Playlist.deleted_at.is_(None),  # Exclude deleted playlists
    )

    # Apply search if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(Playlist.title.ilike(search_term))

    # Order by most recently synced
    query = query.order_by(Playlist.last_synced_at.desc().nullslast())

    # Apply pagination
    offset = (page - 1) * page_size
    playlists = query.offset(offset).limit(page_size).all()

    return playlists


@router.get("/{playlist_id}", response_model=PlaylistWithVideos)
async def get_playlist(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a specific playlist with its videos.

    Returns playlist details along with all videos in the playlist.
    """
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.user_id == current_user.id)
        .first()
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    return playlist


@router.get("/{playlist_id}/videos", response_model=PlaylistVideosCursorResponse)
async def get_playlist_videos(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = Query(None, description="Cursor for pagination (position)"),
    limit: int = Query(20, ge=1, le=100, description="Number of videos to fetch"),
    category_ids: str | None = Query(None, description="Comma-separated category IDs"),
    tag_ids: str | None = Query(None, description="Comma-separated tag IDs"),
    search: str | None = Query(None, description="Search in title and description"),
):
    """
    Get videos from a specific playlist with cursor-based pagination.

    Uses position in playlist as cursor for efficient pagination.
    """
    # Verify playlist exists and belongs to user
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.user_id == current_user.id)
        .first()
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    # Build query for playlist videos
    from app.models.playlist import PlaylistVideo

    # Base query with join
    base_query = (
        db.query(Video, PlaylistVideo.position)
        .join(PlaylistVideo, PlaylistVideo.video_id == Video.id)
        .filter(PlaylistVideo.playlist_id == playlist_id)
    )

    # Apply filters
    if category_ids:
        cat_ids = [int(cid) for cid in category_ids.split(",")]
        base_query = base_query.join(Video.categories).filter(Category.id.in_(cat_ids))

    if tag_ids:
        t_ids = [int(tid) for tid in tag_ids.split(",")]
        base_query = base_query.join(Video.tags).filter(Tag.id.in_(t_ids))

    if search:
        search_term = f"%{search}%"
        base_query = base_query.filter(
            or_(
                Video.title.ilike(search_term),
                Video.description.ilike(search_term),
                Video.channel_title.ilike(search_term),
            )
        )

    # Get total count (before cursor filtering)
    total_count = base_query.count()

    # Apply cursor filter if provided
    if cursor:
        try:
            cursor_position = int(cursor)
            base_query = base_query.filter(PlaylistVideo.position > cursor_position)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor format"
            )

    # Order by position and fetch limit + 1 to check if there are more
    results = base_query.order_by(PlaylistVideo.position.asc()).limit(limit + 1).all()

    # Check if there are more results
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]

    # Extract videos and determine next cursor
    videos = [video for video, _ in results]
    next_cursor = None
    if has_more and results:
        # Use the last video's position as the next cursor
        _, last_position = results[-1]
        next_cursor = str(last_position)

    return PlaylistVideosCursorResponse(
        videos=videos,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )


@router.post("/sync")
async def sync_playlists(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_results: int = Query(50, ge=1, le=100),
):
    """
    Sync playlists from YouTube.

    Fetches user's playlists and updates the database.
    """
    try:
        youtube_service = YouTubeService(current_user)
        playlists, count = youtube_service.fetch_user_playlists(
            db, max_results=max_results
        )

        return {
            "status": "success",
            "playlists_synced": count,
            "total_playlists": len(playlists),
        }

    except Exception as e:
        api_logger.error(
            f"Failed to sync playlists for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync playlists. Please try again later.",
        )


@router.post("/{playlist_id}/sync-videos")
async def sync_playlist_videos(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    max_results: int = Query(50, ge=1, le=100),
):
    """
    Sync videos from a specific playlist.

    Fetches all videos in the playlist and updates the database.
    """
    # Verify playlist exists
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.user_id == current_user.id)
        .first()
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    try:
        youtube_service = YouTubeService(current_user)
        videos = youtube_service.fetch_playlist_videos(
            db, playlist, max_results=max_results
        )

        return {
            "status": "success",
            "videos_synced": len(videos),
            "playlist_id": playlist_id,
            "playlist_title": playlist.title,
        }

    except Exception as e:
        api_logger.error(
            f"Failed to sync playlist {playlist_id} videos for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync playlist videos. Please try again later.",
        )


@router.post("/create-from-filters", response_model=CreatePlaylistFromFiltersResponse)
async def create_playlist_from_filters(
    request: CreatePlaylistFromFiltersRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a YouTube playlist from filtered videos.

    Flow:
    1. Query videos matching the filter criteria
    2. Create playlist on YouTube
    3. Add first 20 videos immediately
    4. Queue remaining videos for background processing (if > 20)
    5. Sync playlist to local database

    Args:
        request: Playlist creation request with title, description, privacy, and filters

    Returns:
        Playlist details, video counts, and background job ID (if applicable)
    """
    try:
        # Build query for filtered videos
        query = db.query(Video).filter(Video.user_id == current_user.id)

        # Apply category filter using EXISTS subquery to avoid duplicates
        if request.filter_params.category_ids:
            from sqlalchemy import exists
            from app.models.video import video_categories

            category_subquery = exists().where(
                video_categories.c.video_id == Video.id,
                video_categories.c.category_id.in_(request.filter_params.category_ids),
            )
            query = query.filter(category_subquery)

        # Apply tag filter using EXISTS subquery
        if request.filter_params.tag_ids:
            from sqlalchemy import exists
            from app.models.video import video_tags

            tag_subquery = exists().where(
                video_tags.c.video_id == Video.id,
                video_tags.c.tag_id.in_(request.filter_params.tag_ids),
            )
            query = query.filter(tag_subquery)

        # Apply search filter
        if request.filter_params.search:
            search_term = f"%{request.filter_params.search}%"
            query = query.filter(
                or_(
                    Video.title.ilike(search_term),
                    Video.description.ilike(search_term),
                )
            )

        # Apply categorization status filter
        if request.filter_params.is_categorized is not None:
            query = query.filter(
                Video.is_categorized == request.filter_params.is_categorized
            )

        # Get all matching videos (no duplicates with subquery approach)
        videos = query.order_by(Video.liked_at.desc()).all()

        if not videos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No videos match the provided filters",
            )

        api_logger.info(
            f"Creating playlist '{request.title}' with {len(videos)} filtered videos for user {current_user.id}"
        )

        # Create playlist on YouTube
        youtube_service = YouTubeService(current_user)
        yt_playlist = youtube_service.create_playlist(
            title=request.title,
            description=request.description,
            privacy_status=request.privacy_status,
        )

        if not yt_playlist:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create playlist on YouTube",
            )

        # Extract YouTube video IDs
        video_ids = [v.youtube_id for v in videos]

        # Add videos immediately if <= 250, otherwise split into batches
        immediate_batch_size = min(250, len(video_ids))
        immediate_videos = video_ids[:immediate_batch_size]
        remaining_videos = video_ids[immediate_batch_size:]

        api_logger.info(
            f"Adding {len(immediate_videos)} videos immediately to playlist {yt_playlist['id']}"
        )

        add_result = youtube_service.add_videos_to_playlist(
            playlist_id=yt_playlist["id"],
            video_ids=immediate_videos,
            position_offset=0,
        )

        # Save playlist to local database
        db_playlist = Playlist(
            user_id=current_user.id,
            youtube_id=yt_playlist["id"],
            title=yt_playlist["snippet"]["title"],
            description=yt_playlist["snippet"].get("description"),
            thumbnail_url=None,  # Will be updated on next sync
            video_count=len(videos),
            published_at=datetime.utcnow(),
            last_synced_at=datetime.utcnow(),
        )
        db.add(db_playlist)
        db.commit()
        db.refresh(db_playlist)

        # Queue remaining videos for background processing
        job_id = None
        if remaining_videos:
            job_id = str(uuid.uuid4())
            api_logger.info(
                f"Queueing {len(remaining_videos)} videos for background processing (job {job_id})"
            )

            # Initialize job data in Redis
            import json

            redis_client = get_redis()
            job_data = {
                "job_id": job_id,
                "user_id": current_user.id,
                "playlist_id": str(db_playlist.id),
                "youtube_playlist_id": yt_playlist["id"],
                "total": len(remaining_videos),
                "completed": 0,
                "failed": 0,
                "status": "pending",
                "results": [],
            }
            redis_client.set(
                f"playlist_job:{job_id}",
                json.dumps(job_data),
                expire=3600,  # 1 hour expiry
            )

            # Queue background job via QStash
            await trigger_playlist_video_addition_job(
                job_id=job_id,
                user_id=current_user.id,
                playlist_id=str(db_playlist.id),
                youtube_playlist_id=yt_playlist["id"],
                video_youtube_ids=remaining_videos,
                position_offset=immediate_batch_size,
            )

        return CreatePlaylistFromFiltersResponse(
            playlist=PlaylistResponse.model_validate(db_playlist),
            total_videos=len(videos),
            added_immediately=add_result["succeeded"],
            queued_for_background=len(remaining_videos) if remaining_videos else 0,
            job_id=job_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Failed to create playlist from filters for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create playlist. Please try again later.",
        )


@router.post("/ai-generate", response_model=PlaylistSuggestion)
async def generate_smart_playlist(
    request: SmartPlaylistRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Generate a smart playlist from a natural language description using AI.

    Uses hybrid retrieval (semantic search + category matching) to find candidates,
    then asks LLM to curate the final selection with reasons and watch order.

    Returns a suggestion that can be confirmed to create the actual YouTube playlist.
    """
    try:
        ai_service = AIService()

        # If refining, load previous suggestion from Redis
        previous_video_ids = None
        if request.refinement and request.previous_suggestion_id:
            redis_client = get_redis()
            cached = redis_client.get(
                f"smart_playlist:{request.previous_suggestion_id}"
            )
            if cached:
                import json

                prev = json.loads(cached)
                previous_video_ids = [v["video_id"] for v in prev.get("videos", [])]

        result = await ai_service.generate_smart_playlist(
            description=request.description,
            user_id=current_user.id,
            max_videos=request.max_videos,
            db=db,
            refinement=request.refinement,
            previous_video_ids=previous_video_ids,
        )

        return PlaylistSuggestion(**result)

    except Exception as e:
        api_logger.error(
            f"Smart playlist generation failed for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate smart playlist. Please try again.",
        )


@router.post("/ai-generate/confirm", response_model=CreatePlaylistFromFiltersResponse)
async def confirm_smart_playlist(
    request: SmartPlaylistConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Confirm a smart playlist suggestion and create it on YouTube.

    Takes a suggestion_id from a previous ai-generate call, retrieves the
    cached suggestion, and creates the playlist on YouTube.
    """
    import json

    redis_client = get_redis()
    cached = redis_client.get(f"smart_playlist:{request.suggestion_id}")

    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion expired or not found. Please generate a new one.",
        )

    suggestion = json.loads(cached)

    # Verify the suggestion belongs to this user
    if suggestion.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This suggestion does not belong to you.",
        )

    try:
        # Get video IDs in watch order
        sorted_videos = sorted(suggestion["videos"], key=lambda v: v["order_position"])
        video_ids = [v["video_id"] for v in sorted_videos]

        # Fetch the actual videos to get YouTube IDs
        videos = (
            db.query(Video)
            .filter(Video.id.in_(video_ids), Video.user_id == current_user.id)
            .all()
        )

        video_map = {v.id: v for v in videos}
        youtube_ids = [
            video_map[vid].youtube_id for vid in video_ids if vid in video_map
        ]

        if not youtube_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid videos found in the suggestion.",
            )

        # Create playlist on YouTube
        youtube_service = YouTubeService(current_user)
        yt_playlist = youtube_service.create_playlist(
            title=suggestion["title"],
            description=suggestion["description"],
            privacy_status=request.privacy_status,
        )

        if not yt_playlist:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create playlist on YouTube.",
            )

        # Add videos (up to 250 immediately)
        immediate_batch = youtube_ids[:250]
        remaining = youtube_ids[250:]

        add_result = youtube_service.add_videos_to_playlist(
            playlist_id=yt_playlist["id"],
            video_ids=immediate_batch,
            position_offset=0,
        )

        # Save playlist to local database
        db_playlist = Playlist(
            user_id=current_user.id,
            youtube_id=yt_playlist["id"],
            title=yt_playlist["snippet"]["title"],
            description=yt_playlist["snippet"].get("description"),
            thumbnail_url=None,
            video_count=len(youtube_ids),
            published_at=datetime.utcnow(),
            last_synced_at=datetime.utcnow(),
        )
        db.add(db_playlist)
        db.commit()
        db.refresh(db_playlist)

        # Queue remaining if needed
        job_id = None
        if remaining:
            job_id = str(uuid.uuid4())
            job_data = {
                "job_id": job_id,
                "user_id": current_user.id,
                "playlist_id": str(db_playlist.id),
                "youtube_playlist_id": yt_playlist["id"],
                "total": len(remaining),
                "completed": 0,
                "failed": 0,
                "status": "pending",
                "results": [],
            }
            redis_client.set(
                f"playlist_job:{job_id}",
                json.dumps(job_data),
                expire=3600,
            )
            await trigger_playlist_video_addition_job(
                job_id=job_id,
                user_id=current_user.id,
                playlist_id=str(db_playlist.id),
                youtube_playlist_id=yt_playlist["id"],
                video_youtube_ids=remaining,
                position_offset=len(immediate_batch),
            )

        # Clean up the suggestion from cache
        redis_client.delete(f"smart_playlist:{request.suggestion_id}")

        return CreatePlaylistFromFiltersResponse(
            playlist=PlaylistResponse.model_validate(db_playlist),
            total_videos=len(youtube_ids),
            added_immediately=add_result["succeeded"],
            queued_for_background=len(remaining),
            job_id=job_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Failed to confirm smart playlist for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create playlist. Please try again.",
        )
