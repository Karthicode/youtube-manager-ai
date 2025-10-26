"""Playlists router for managing YouTube playlists."""

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
)
from app.schemas.video import VideoResponse
from app.services.youtube_service import YouTubeService
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
    query = db.query(Playlist).filter(Playlist.user_id == current_user.id)

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


@router.get("/{playlist_id}/videos", response_model=List[VideoResponse])
async def get_playlist_videos(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_ids: str | None = Query(None, description="Comma-separated category IDs"),
    tag_ids: str | None = Query(None, description="Comma-separated tag IDs"),
    search: str | None = Query(None, description="Search in title and description"),
):
    """
    Get videos from a specific playlist with filtering.

    Supports same filtering as liked videos endpoint.
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
    from app.models.category import Category
    from app.models.tag import Tag

    query = (
        db.query(Video)
        .join(PlaylistVideo, PlaylistVideo.video_id == Video.id)
        .filter(PlaylistVideo.playlist_id == playlist_id)
    )

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

    # Order by position in playlist
    query = query.order_by(PlaylistVideo.position.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    videos = query.offset(offset).limit(page_size).all()

    return videos


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync playlists: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync playlist videos: {str(e)}",
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
                ex=3600,  # 1 hour expiry
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
        api_logger.error(f"Failed to create playlist from filters: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create playlist: {str(e)}",
        )
