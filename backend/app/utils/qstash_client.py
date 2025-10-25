"""QStash client for triggering background jobs via Upstash."""

import httpx

from app.config import settings
from app.logger import api_logger


async def trigger_categorization_job(
    job_id: str,
    user_id: int,
    video_ids: list[int],
    max_concurrent: int = 10,
    worker_url: str | None = None,
) -> dict:
    """
    Trigger a categorization job via QStash.

    Args:
        job_id: Unique job identifier
        user_id: User ID
        video_ids: List of video IDs to categorize
        max_concurrent: Maximum concurrent batches
        worker_url: Worker endpoint URL (auto-detected if None)

    Returns:
        QStash response with message ID

    Raises:
        httpx.HTTPError: If QStash request fails
    """
    # If QStash is not configured, run locally (development mode)
    if not settings.qstash_token:
        api_logger.warning(
            "QStash not configured, job will run synchronously (dev mode)"
        )
        return {
            "mode": "local",
            "message": "Job will run in background without QStash",
        }

    # Determine worker URL
    if not worker_url:
        # In production, use the same domain
        if settings.is_production:
            worker_url = f"{settings.frontend_url}/api/v1/worker/categorize-batch"
        else:
            # Local development
            worker_url = "http://localhost:8000/api/v1/worker/categorize-batch"

    # Prepare payload
    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "video_ids": video_ids,
        "max_concurrent": max_concurrent,
    }

    # Publish to QStash
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.qstash_url,
            json={
                "url": worker_url,
                "body": payload,
                "headers": {
                    "Content-Type": "application/json",
                },
            },
            headers={
                "Authorization": f"Bearer {settings.qstash_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()

        api_logger.info(
            f"QStash job triggered: {job_id}, message_id={result.get('messageId')}"
        )
        return result
