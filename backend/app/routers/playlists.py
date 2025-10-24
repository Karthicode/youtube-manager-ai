"""Playlists router for managing YouTube playlists."""

from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.playlist import Playlist
from app.models.video import Video
from app.schemas.playlist import PlaylistResponse, PlaylistWithVideos
from app.schemas.video import VideoResponse
from app.services.youtube_service import YouTubeService

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
