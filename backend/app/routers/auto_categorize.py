"""User-initiated auto-categorize retry endpoint.

Reuses the same sync+categorize flow as the daily cron (via
``AutoCategorizeService.run_for_user``) but is authenticated with the user's
JWT instead of a QStash signature. Intended to back the dashboard's "Retry
now" banner when the last automatic run failed or is stale.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.logger import api_logger
from app.models.user import User
from app.services.auto_categorize_service import AutoCategorizeService

router = APIRouter(prefix="/auto-categorize", tags=["auto-categorize"])


@router.post("/retry")
async def retry_auto_categorize(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually re-run the sync + categorize flow for the current user.

    Returns the same payload shape as ``AutoCategorizeService.run_for_user``:
    ``status`` is one of ``skipped``, ``no_videos``, ``triggered``, or
    ``failed``. When ``triggered``, the response includes ``job_id`` so the
    frontend can subscribe to the SSE progress stream.
    """
    try:
        result = await AutoCategorizeService.run_for_user(db, current_user)
    except Exception as e:
        api_logger.error(
            f"Unexpected error in auto-categorize retry for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to run auto-categorize retry",
        )

    if result.get("status") == "failed":
        # Surface failures as 4xx/5xx so the frontend can show an error toast
        # instead of silently reporting success.
        stage = result.get("stage", "unknown")
        raise HTTPException(
            status_code=502 if stage == "trigger" else 500,
            detail={
                "message": "Auto-categorize retry failed",
                "stage": stage,
                "error": result.get("error"),
            },
        )

    return result
