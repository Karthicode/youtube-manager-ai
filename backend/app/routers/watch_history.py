"""Router for watch history / continue watching endpoints."""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.watch_history import (
    WatchHistoryListResponse,
    WatchHistoryResponse,
    WatchHistoryUpsert,
)
from app.services import watch_history_service
from app.utils.cache_invalidation import invalidate_continue_watching

router = APIRouter(prefix="/watch-history", tags=["Watch History"])

CONTINUE_WATCHING_TTL = 60  # 60 seconds


@router.post("/position", response_model=WatchHistoryResponse | None)
def save_position(
    body: WatchHistoryUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchHistoryResponse | None:
    """Save or update the playback position for a video."""
    result = watch_history_service.upsert_position(
        db=db,
        user_id=current_user.id,
        youtube_id=body.youtube_id,
        position_seconds=body.position_seconds,
        duration_seconds=body.duration_seconds,
    )
    invalidate_continue_watching(current_user.id)
    return result


@router.get("/continue-watching", response_model=WatchHistoryListResponse)
def get_continue_watching(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchHistoryListResponse:
    """Return in-progress videos ordered by most recently watched."""
    redis = get_redis()
    cache_key = f"continue_watching:{current_user.id}:{limit}"
    cached = redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        return WatchHistoryListResponse(**data)

    items = watch_history_service.get_continue_watching(
        db=db,
        user_id=current_user.id,
        limit=limit,
    )
    result = WatchHistoryListResponse(items=items, total=len(items))
    redis.set(
        cache_key,
        json.dumps(result.model_dump(mode="json")),
        expire=CONTINUE_WATCHING_TTL,
    )
    return result


@router.get("/position/{youtube_id}", response_model=WatchHistoryResponse | None)
def get_position(
    youtube_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchHistoryResponse | None:
    """Return the saved playback position for a specific video."""
    return watch_history_service.get_position(
        db=db,
        user_id=current_user.id,
        youtube_id=youtube_id,
    )


@router.delete("/{history_id}", status_code=204)
def delete_entry(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a watch history entry."""
    watch_history_service.delete_history_entry(
        db=db,
        user_id=current_user.id,
        history_id=history_id,
    )
    invalidate_continue_watching(current_user.id)
