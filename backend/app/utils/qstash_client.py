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
        # Use backend URL for worker endpoints
        worker_url = f"{settings.backend_url}/api/v1/worker/categorize-batch"

    # Publish to QStash queue
    # Split videos into batches and send one message per batch
    # Each message contains only the video IDs for that specific batch
    queue_name = settings.qstash_queue_name
    queue_url = f"https://qstash.upstash.io/v2/enqueue/{queue_name}/{worker_url}"

    api_logger.info(
        f"Triggering QStash queue '{queue_name}' for job {job_id} with {len(video_ids)} videos"
    )

    # Split into batches of 10 videos each
    batch_size = 10
    total_batches = (len(video_ids) + batch_size - 1) // batch_size

    async with httpx.AsyncClient() as client:
        # Queue each batch with its specific video IDs
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(video_ids))
            batch_video_ids = video_ids[start_idx:end_idx]

            # Each message gets only the videos for this batch
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "video_ids": batch_video_ids,  # Only this batch's videos!
                "max_concurrent": max_concurrent,
            }

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
                api_logger.debug(f"Queued batch {batch_num+1}/{total_batches}: videos {start_idx}-{end_idx-1}")
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


async def trigger_playlist_video_addition_job(
    job_id: str,
    user_id: int,
    playlist_id: str,
    youtube_playlist_id: str,
    video_youtube_ids: list[str],
    position_offset: int = 0,
    worker_url: str | None = None,
) -> dict:
    """
    Trigger a playlist video addition job via QStash.

    Args:
        job_id: Unique job identifier
        user_id: User ID
        playlist_id: Local database playlist ID
        youtube_playlist_id: YouTube playlist ID
        video_youtube_ids: List of YouTube video IDs to add
        position_offset: Starting position in playlist
        worker_url: Worker endpoint URL (auto-detected if None)

    Returns:
        QStash response with message ID

    Raises:
        httpx.HTTPError: If QStash request fails
    """
    # If QStash is not configured, run locally (development mode)
    if not settings.qstash_token:
        api_logger.warning(
            "QStash not configured, playlist videos will be added synchronously (dev mode)"
        )
        return {
            "mode": "local",
            "message": "Job will run in background without QStash",
        }

    # Determine worker URL
    if not worker_url:
        # Use backend URL for worker endpoints
        worker_url = f"{settings.backend_url}/api/v1/worker/add-playlist-videos"

    # Publish to QStash queue
    # Split videos into batches and send one message per batch
    queue_name = settings.qstash_queue_name
    queue_url = f"https://qstash.upstash.io/v2/enqueue/{queue_name}/{worker_url}"

    api_logger.info(
        f"Triggering QStash queue '{queue_name}' for job {job_id} with {len(video_youtube_ids)} videos"
    )

    # Split into batches of 10 videos each
    batch_size = 10
    total_batches = (len(video_youtube_ids) + batch_size - 1) // batch_size

    async with httpx.AsyncClient() as client:
        # Queue each batch with its specific video IDs
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(video_youtube_ids))
            batch_youtube_ids = video_youtube_ids[start_idx:end_idx]

            # Each message gets only the videos for this batch
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "playlist_id": playlist_id,
                "youtube_playlist_id": youtube_playlist_id,
                "video_youtube_ids": batch_youtube_ids,
                "position_offset": position_offset + start_idx,
            }

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
                api_logger.debug(
                    f"Queued batch {batch_num+1}/{total_batches}: videos {start_idx}-{end_idx-1}"
                )
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
