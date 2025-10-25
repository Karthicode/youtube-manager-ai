"""Progress tracking router for categorization tasks."""

from typing import Annotated
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.models.user import User
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress")


@router.get("/categorization")
async def get_categorization_progress(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get real-time progress of categorization task for current user.

    Returns:
        Progress data including total, completed, failed counts and current video
    """
    progress = ProgressService.get_progress(current_user.id)

    if not progress:
        return {
            "status": "idle",
            "total": 0,
            "completed": 0,
            "failed": 0,
            "current_video": None,
        }

    return progress
