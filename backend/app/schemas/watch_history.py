"""Schemas for watch history endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class WatchHistoryUpsert(BaseModel):
    """Request body for saving playback position."""

    youtube_id: str
    position_seconds: float
    duration_seconds: Optional[int] = None


class WatchHistoryResponse(BaseModel):
    """Response model for a watch history entry."""

    id: int
    video_id: int
    youtube_id: str
    title: str
    thumbnail_url: Optional[str]
    channel_title: Optional[str]
    position_seconds: float
    duration_seconds: Optional[int]
    progress_percent: float
    is_completed: bool
    watched_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchHistoryListResponse(BaseModel):
    """Response model for a list of watch history entries."""

    items: List[WatchHistoryResponse]
    total: int
