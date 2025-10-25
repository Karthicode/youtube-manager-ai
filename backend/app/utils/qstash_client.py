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

    # Prepare payload - send ALL video_ids, worker will process incrementally
    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "video_ids": video_ids,
        "max_concurrent": max_concurrent,
    }

    # Publish to QStash queue
    # We send ONE message with all video IDs
    # Worker processes one batch (10 videos) per invocation
    # QStash will retry/requeue automatically based on response
    queue_name = settings.qstash_queue_name
    queue_url = f"https://qstash.upstash.io/v2/enqueue/{queue_name}/{worker_url}"

    api_logger.info(
        f"Triggering QStash queue '{queue_name}' for job {job_id} with {len(video_ids)} videos"
    )

    # Send 84 messages (one per batch) to QStash
    # This ensures all batches are queued and processed with parallelism=2
    batch_size = 10
    total_batches = (len(video_ids) + batch_size - 1) // batch_size

    async with httpx.AsyncClient() as client:
        # Queue all batches at once
        for batch_num in range(total_batches):
            try:
                response = await client.post(
                    queue_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.qstash_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
            except Exception as e:
                api_logger.error(f"Failed to queue batch {batch_num}: {e}")

        api_logger.info(
            f"QStash: Queued {total_batches} batch jobs for job_id={job_id}"
        )
        return {
            "mode": "qstash",
            "batches_queued": total_batches,
            "job_id": job_id,
        }
