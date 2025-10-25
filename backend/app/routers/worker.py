"""Worker endpoints for background job processing via QStash."""

import asyncio

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from qstash import Receiver
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import api_logger
from app.models.video import Video
from app.services.ai_service import AIService
from app.redis_client import get_redis


router = APIRouter(prefix="/worker", tags=["worker"])


# Redis helper functions (same as in videos.py)
def get_job_data(job_id: str) -> dict | None:
    """Get job data from Redis."""
    import json

    redis_client = get_redis()
    data = redis_client.get(f"categorization_job:{job_id}")
    return json.loads(data) if data else None


def set_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set job data in Redis with expiration (default 1 hour)."""
    import json

    redis_client = get_redis()
    redis_client.set(f"categorization_job:{job_id}", json.dumps(data), expire=expire)


class JobPayload(BaseModel):
    """Payload for categorization job."""

    job_id: str
    user_id: int
    video_ids: list[int]
    max_concurrent: int = 10


@router.post("/categorize-batch")
async def process_categorization_job(
    request: Request,
    upstash_signature: str | None = Header(None, alias="Upstash-Signature"),
):
    """
    Worker endpoint called by QStash to process categorization jobs.

    This runs the heavy AI workload outside of Vercel's request timeout.

    Flow:
    1. Verify QStash signature (security)
    2. Parse request body
    3. Fetch job data from Redis
    4. Process videos in batches with OpenAI
    5. Update progress in Redis
    6. Save results to database
    """
    from app.database import SessionLocal

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature using QStash SDK
    if settings.qstash_token and settings.qstash_current_signing_key:
        try:
            receiver = Receiver(
                current_signing_key=settings.qstash_current_signing_key,
                next_signing_key=settings.qstash_next_signing_key,
            )

            # Construct the full URL for verification
            base_url = settings.frontend_url.rstrip("/")
            full_url = f"{base_url}/api/v1/worker/categorize-batch"

            # Verify the signature - QStash SDK handles the verification
            receiver.verify(
                signature=upstash_signature,
                body=body.decode("utf-8"),
                url=full_url,
            )
            api_logger.info("QStash signature verified successfully")

        except Exception as e:
            api_logger.error(f"QStash signature verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

    # Parse JSON payload
    try:
        import json

        payload_dict = json.loads(body.decode("utf-8"))
        payload = JobPayload(**payload_dict)
    except Exception as e:
        api_logger.error(f"Failed to parse payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {str(e)}",
        )

    job_id = payload.job_id
    api_logger.info(
        f"Worker processing job {job_id} with {len(payload.video_ids)} videos"
    )

    # Get job data from Redis
    job_data = get_job_data(job_id)
    if not job_data:
        api_logger.error(f"Job {job_id} not found in Redis")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Update status to running
    job_data["status"] = "running"
    set_job_data(job_id, job_data)

    # Start processing in background and return immediately
    # Vercel has 10s timeout, so we can't wait for completion
    asyncio.create_task(
        _run_categorization_job(
            job_id, payload.user_id, payload.video_ids, payload.max_concurrent
        )
    )

    api_logger.info(f"Job {job_id} started in background")
    return {"status": "accepted", "job_id": job_id}


async def _run_categorization_job(
    job_id: str, user_id: int, video_ids: list[int], max_concurrent: int
):
    """Run categorization job in background."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        await _process_batch_categorization(
            db, job_id, user_id, video_ids, max_concurrent
        )
    except Exception as e:
        api_logger.error(f"Worker job {job_id} failed: {e}", exc_info=True)
        job_data = get_job_data(job_id)
        if job_data:
            job_data["status"] = "error"
            job_data["error"] = str(e)
            set_job_data(job_id, job_data)
    finally:
        db.close()


async def _process_batch_categorization(
    db: Session,
    job_id: str,
    user_id: int,
    video_ids: list[int],
    max_concurrent: int = 10,
):
    """
    Process batch categorization with batched OpenAI calls.

    Args:
        db: Database session
        job_id: Redis job ID
        user_id: User ID for cache invalidation
        video_ids: List of video IDs to categorize
        max_concurrent: Maximum concurrent batches (default 10)
    """
    ai_service = AIService()
    semaphore = asyncio.Semaphore(max_concurrent)

    # Fetch ALL videos upfront to avoid connection pool issues
    api_logger.info(f"Fetching all {len(video_ids)} videos from database...")
    all_videos = db.query(Video).filter(Video.id.in_(video_ids)).all()

    # Create a mapping of video_id -> video for quick lookup
    video_map = {video.id: video for video in all_videos}
    api_logger.info(f"Loaded {len(video_map)} videos into memory")

    # Process videos in batches of 10 for GPT batching efficiency
    batch_size = 10

    async def categorize_batch_with_progress(batch_video_ids: list[int]):
        """Categorize a batch of videos with a single API call."""
        async with semaphore:
            try:
                # Check if job is paused/cancelled
                data = get_job_data(job_id)
                if not data:
                    api_logger.warning(f"Job {job_id} not found in Redis")
                    return

                # Wait while paused
                while data.get("paused", False):
                    await asyncio.sleep(1)
                    data = get_job_data(job_id)
                    if not data or data["status"] in [
                        "completed",
                        "error",
                        "cancelled",
                    ]:
                        return

                # Check if cancelled
                if data["status"] == "cancelled":
                    api_logger.info(f"Job {job_id} was cancelled, stopping batch")
                    return

                # Get videos from the pre-loaded map
                videos = [
                    video_map[vid_id]
                    for vid_id in batch_video_ids
                    if vid_id in video_map
                ]
                if not videos:
                    api_logger.error(f"No videos found for batch: {batch_video_ids}")
                    return

                api_logger.info(
                    f"Batch categorizing {len(videos)} videos with 1 API call"
                )

                # Update current video in Redis
                data = get_job_data(job_id)
                if data:
                    data["current_video"] = f"Batch of {len(videos)} videos"
                    set_job_data(job_id, data)

                # Single API call for all videos in batch!
                categorizations = await ai_service.categorize_videos_batch_async(videos)

                # Apply categorizations to all videos
                for video, categorization in zip(videos, categorizations):
                    try:
                        ai_service.apply_categorization(db, video, categorization)

                        # Update progress
                        data = get_job_data(job_id)
                        if data:
                            data["completed"] += 1
                            data["results"].append(
                                {
                                    "video_id": video.id,
                                    "title": video.title,
                                    "success": True,
                                    "categories": categorization.primary_categories
                                    + categorization.secondary_categories,
                                    "tags": categorization.tags,
                                }
                            )
                            set_job_data(job_id, data)
                    except Exception as e:
                        api_logger.error(
                            f"Failed to apply categorization for video {video.id}: {e}"
                        )
                        data = get_job_data(job_id)
                        if data:
                            data["failed"] += 1
                            data["results"].append(
                                {
                                    "video_id": video.id,
                                    "title": video.title,
                                    "success": False,
                                    "error": str(e),
                                }
                            )
                            set_job_data(job_id, data)

                api_logger.info(
                    f"Successfully categorized batch of {len(videos)} videos"
                )

            except Exception as e:
                api_logger.error(f"Failed to categorize batch: {e}", exc_info=True)
                # Mark all videos in batch as failed
                data = get_job_data(job_id)
                if data:
                    for vid_id in batch_video_ids:
                        data["failed"] += 1
                        data["results"].append(
                            {
                                "video_id": vid_id,
                                "title": f"Video {vid_id}",
                                "success": False,
                                "error": str(e),
                            }
                        )
                    set_job_data(job_id, data)

    # Split videos into batches of 10
    video_batches = [
        video_ids[i : i + batch_size] for i in range(0, len(video_ids), batch_size)
    ]

    api_logger.info(
        f"Split {len(video_ids)} videos into {len(video_batches)} batches of ~{batch_size}"
    )

    # Run batch categorizations in parallel (max_concurrent batches at a time)
    tasks = [categorize_batch_with_progress(batch) for batch in video_batches]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Mark job as complete in Redis
    data = get_job_data(job_id)
    if data and data["status"] != "cancelled":
        data["status"] = "completed"
        data["current_video"] = None
        set_job_data(job_id, data, expire=7200)  # Keep result for 2 hours

    api_logger.info(
        f"Job {job_id} completed: {data['completed'] if data else 0} successful, "
        f"{data['failed'] if data else 0} failed"
    )
