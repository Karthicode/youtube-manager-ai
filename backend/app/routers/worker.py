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
from app.services.progress_service import ProgressService
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


def get_playlist_job_data(job_id: str) -> dict | None:
    """Get playlist job data from Redis."""
    import json

    redis_client = get_redis()
    data = redis_client.get(f"playlist_job:{job_id}")
    return json.loads(data) if data else None


def set_playlist_job_data(job_id: str, data: dict, expire: int = 3600) -> None:
    """Set playlist job data in Redis with expiration (default 1 hour)."""
    import json

    redis_client = get_redis()
    redis_client.set(f"playlist_job:{job_id}", json.dumps(data), expire=expire)


class JobPayload(BaseModel):
    """Payload for categorization job."""

    job_id: str
    user_id: int
    video_ids: list[int]
    max_concurrent: int = 10


class PlaylistJobPayload(BaseModel):
    """Payload for playlist video addition job."""

    job_id: str
    user_id: int
    playlist_id: str
    youtube_playlist_id: str
    video_youtube_ids: list[str]
    position_offset: int = 0


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
            base_url = settings.backend_url.rstrip("/")
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

    # Process videos synchronously - Vercel limits to ~10s, so we process ONE batch only
    # Each QStash call will process one batch

    db = SessionLocal()

    try:
        # Process just ONE batch (10 videos) per QStash invocation
        result = await _process_one_batch(
            db, job_id, payload.user_id, payload.video_ids
        )

        api_logger.info(f"Job {job_id} batch processed: {result}")
        return {"status": "success", "job_id": job_id, **result}

    except Exception as e:
        api_logger.error(f"Worker job {job_id} failed: {e}", exc_info=True)
        job_data = get_job_data(job_id)
        if job_data:
            job_data["status"] = "error"
            job_data["error"] = str(e)
            set_job_data(job_id, job_data)

            # Update user progress to error state
            ProgressService.set_progress(
                payload.user_id,
                {
                    "status": "error",
                    "total": job_data.get("total", 0),
                    "completed": job_data.get("completed", 0),
                    "failed": job_data.get("failed", 0),
                    "current_video": None,
                    "error": str(e),
                },
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job processing failed: {str(e)}",
        )
    finally:
        db.close()


async def _process_one_batch(
    db: Session, job_id: str, user_id: int, video_ids: list[int]
) -> dict:
    """
    Process a batch of videos (typically 10, sent by QStash).

    Args:
        video_ids: Specific video IDs to process in this batch

    Returns:
        dict with processed count and whether job is complete
    """
    ai_service = AIService()

    # Get job data
    job_data = get_job_data(job_id)
    if not job_data:
        return {"processed": 0, "complete": False, "error": "Job not found"}

    api_logger.info(
        f"Processing batch of {len(video_ids)} videos from job {job_id}: {video_ids}"
    )

    # Fetch videos for this batch
    videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
    video_map = {v.id: v for v in videos}

    # Filter out already categorized videos (race condition protection)
    uncategorized_videos = [
        video_map[vid]
        for vid in video_ids
        if vid in video_map and not video_map[vid].is_categorized
    ]

    if not uncategorized_videos:
        api_logger.info("All videos in this batch already categorized, skipping")
        return {"processed": 0, "complete": False}

    # Categorize with single API call
    categorizations = await ai_service.categorize_videos_batch_async(
        uncategorized_videos
    )

    # Apply and update progress
    # Collect results for this batch first
    batch_results = []

    for video, categorization in zip(uncategorized_videos, categorizations):
        video_id = video.id
        video_title = video.title

        try:
            # Re-fetch video to ensure fresh state (especially after rollbacks)
            fresh_video = db.query(Video).filter(Video.id == video_id).first()
            if not fresh_video:
                api_logger.warning(f"Video {video_id} not found, skipping")
                continue

            # Double-check if already categorized (race condition)
            if fresh_video.is_categorized:
                api_logger.info(f"Video {video_id} already categorized, skipping")
                continue

            # Apply categorization - this may fail if another worker got there first
            try:
                ai_service.apply_categorization(db, fresh_video, categorization)

                # Success! Add to results
                batch_results.append(
                    {
                        "video_id": video_id,
                        "title": video_title,
                        "success": True,
                        "categories": categorization.primary_categories
                        + categorization.secondary_categories,
                        "tags": categorization.tags,
                    }
                )
                api_logger.info(f"Successfully categorized video {video_id}")

            except Exception as apply_error:
                # Check if it's a duplicate key error during commit
                error_str = str(apply_error).lower()
                if (
                    "duplicate key" in error_str
                    or "uniqueviolation" in error_str
                    or "integrity" in error_str
                ):
                    api_logger.info(
                        f"Video {video_id} already categorized by concurrent worker, skipping (expected behavior)"
                    )
                    # Rollback to clean session state
                    db.rollback()
                    # Don't add to batch_results - this video is already processed
                    continue
                else:
                    # Some other error during apply - re-raise to outer catch
                    raise

        except Exception as e:
            # Unexpected error - log and mark as failed
            api_logger.error(
                f"Unexpected error categorizing video {video_id}: {e}", exc_info=True
            )
            db.rollback()
            batch_results.append(
                {
                    "video_id": video_id,
                    "title": video_title,
                    "success": False,
                    "error": str(e),
                }
            )

    # Re-fetch latest job data and append batch results atomically
    latest_job_data = get_job_data(job_id)
    if latest_job_data:
        # Check which results are actually new (not already in results)
        existing_video_ids = {r["video_id"] for r in latest_job_data.get("results", [])}
        new_results = [
            r for r in batch_results if r["video_id"] not in existing_video_ids
        ]

        if new_results:
            latest_job_data["results"].extend(new_results)
            latest_job_data["completed"] = len(latest_job_data["results"])
            latest_job_data["failed"] = sum(
                1 for r in latest_job_data["results"] if not r.get("success", True)
            )
            set_job_data(job_id, latest_job_data)
            api_logger.info(f"Added {len(new_results)} new results to job {job_id}")
        else:
            api_logger.info(
                "No new results to add (all already processed by other workers)"
            )
    else:
        api_logger.error(f"Could not fetch latest job data for {job_id}")

    # Re-fetch job data to get accurate count (in case other workers updated)
    latest_job_data = get_job_data(job_id)
    if latest_job_data:
        # Count actual processed videos from results array (source of truth)
        actual_completed = len(latest_job_data.get("results", []))
        actual_failed = sum(
            1 for r in latest_job_data.get("results", []) if not r.get("success", True)
        )
        actual_successful = actual_completed - actual_failed

        # Update user-specific progress for SSE endpoint
        ProgressService.set_progress(
            user_id,
            {
                "status": latest_job_data["status"],
                "total": latest_job_data["total"],
                "completed": actual_successful,
                "failed": actual_failed,
                "current_video": f"Processed {actual_completed} of {latest_job_data['total']} videos",
            },
        )

        api_logger.info(
            f"Job {job_id}: Progress {actual_completed}/{latest_job_data['total']} "
            f"({(actual_completed / latest_job_data['total'] * 100):.1f}%) - "
            f"{actual_successful} successful, {actual_failed} failed"
        )

    # Invalidate cache after each batch so stats update in real-time
    from app.routers.videos import invalidate_user_stats_cache

    invalidate_user_stats_cache(user_id)

    # Check if job is complete by comparing results count with total
    is_complete = latest_job_data and latest_job_data.get(
        "completed", 0
    ) >= latest_job_data.get("total", 0)

    if is_complete:
        # Mark job as completed
        final_job_data = get_job_data(job_id)
        if final_job_data:
            final_job_data["status"] = "completed"
            final_job_data["current_video"] = None
            set_job_data(job_id, final_job_data, expire=7200)

            # Count actual results for final stats
            actual_completed = len(final_job_data.get("results", []))
            actual_failed = sum(
                1
                for r in final_job_data.get("results", [])
                if not r.get("success", True)
            )
            actual_successful = actual_completed - actual_failed

            # Update user progress to completed
            ProgressService.set_progress(
                user_id,
                {
                    "status": "completed",
                    "total": final_job_data["total"],
                    "completed": actual_successful,
                    "failed": actual_failed,
                    "current_video": None,
                },
            )

            api_logger.info(
                f"Job {job_id} completed! {actual_successful} videos categorized successfully, "
                f"{actual_failed} failed out of {actual_completed} total processed."
            )

    return {
        "processed": len(video_ids),
        "complete": is_complete,
    }


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


@router.post("/add-playlist-videos")
async def process_playlist_video_addition_job(
    request: Request,
    upstash_signature: str | None = Header(None, alias="Upstash-Signature"),
):
    """
    Worker endpoint called by QStash to add videos to YouTube playlists.

    This runs the YouTube API calls outside of Vercel's request timeout.

    Flow:
    1. Verify QStash signature (security)
    2. Parse request body
    3. Fetch job data from Redis
    4. Add videos to YouTube playlist in batch
    5. Update progress in Redis
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
            base_url = settings.backend_url.rstrip("/")
            full_url = f"{base_url}/api/v1/worker/add-playlist-videos"

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
        payload = PlaylistJobPayload(**payload_dict)
    except Exception as e:
        api_logger.error(f"Failed to parse payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {str(e)}",
        )

    job_id = payload.job_id
    api_logger.info(
        f"Worker processing playlist job {job_id} with {len(payload.video_youtube_ids)} videos"
    )

    # Get job data from Redis
    job_data = get_playlist_job_data(job_id)
    if not job_data:
        api_logger.error(f"Playlist job {job_id} not found in Redis")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Update status to running
    job_data["status"] = "running"
    set_playlist_job_data(job_id, job_data)

    db = SessionLocal()

    try:
        # Process this batch of videos
        result = await _process_playlist_video_batch(
            db,
            job_id,
            payload.user_id,
            payload.youtube_playlist_id,
            payload.video_youtube_ids,
            payload.position_offset,
        )

        api_logger.info(f"Playlist job {job_id} batch processed: {result}")
        return {"status": "success", "job_id": job_id, **result}

    except Exception as e:
        api_logger.error(f"Worker playlist job {job_id} failed: {e}", exc_info=True)
        job_data = get_playlist_job_data(job_id)
        if job_data:
            job_data["status"] = "error"
            job_data["error"] = str(e)
            set_playlist_job_data(job_id, job_data)

            # Update user progress to error state
            ProgressService.set_progress(
                payload.user_id,
                {
                    "status": "error",
                    "total": job_data.get("total", 0),
                    "completed": job_data.get("completed", 0),
                    "failed": job_data.get("failed", 0),
                    "current_video": None,
                    "error": str(e),
                },
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job processing failed: {str(e)}",
        )
    finally:
        db.close()


async def _process_playlist_video_batch(
    db: Session,
    job_id: str,
    user_id: int,
    youtube_playlist_id: str,
    video_youtube_ids: list[str],
    position_offset: int,
) -> dict:
    """
    Process a batch of videos to add to YouTube playlist.

    Args:
        db: Database session
        job_id: Job ID for tracking
        user_id: User ID
        youtube_playlist_id: YouTube playlist ID
        video_youtube_ids: YouTube video IDs to add
        position_offset: Starting position in playlist

    Returns:
        dict with processed count and whether job is complete
    """
    from app.models.user import User
    from app.services.youtube_service import YouTubeService

    # Get user for YouTube service
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        api_logger.error(f"User {user_id} not found")
        return {"processed": 0, "complete": False, "error": "User not found"}

    # Get job data
    job_data = get_playlist_job_data(job_id)
    if not job_data:
        return {"processed": 0, "complete": False, "error": "Job not found"}

    api_logger.info(
        f"Processing batch of {len(video_youtube_ids)} videos for playlist {youtube_playlist_id}"
    )

    # Add videos to YouTube playlist
    youtube_service = YouTubeService(user)
    add_result = youtube_service.add_videos_to_playlist(
        playlist_id=youtube_playlist_id,
        video_ids=video_youtube_ids,
        position_offset=position_offset,
    )

    # Update job data with results
    latest_job_data = get_playlist_job_data(job_id)
    if latest_job_data:
        # Append batch results
        latest_job_data["completed"] += add_result["succeeded"]
        latest_job_data["failed"] += add_result["failed"]

        # Add detailed results
        for i, video_id in enumerate(video_youtube_ids):
            if i < add_result["succeeded"]:
                latest_job_data["results"].append(
                    {
                        "video_id": video_id,
                        "success": True,
                    }
                )
            else:
                # Find matching failure
                failure = next(
                    (f for f in add_result["failures"] if f["video_id"] == video_id),
                    None,
                )
                latest_job_data["results"].append(
                    {
                        "video_id": video_id,
                        "success": False,
                        "error": failure["error"] if failure else "Unknown error",
                    }
                )

        set_playlist_job_data(job_id, latest_job_data)

        # Update user-specific progress for SSE endpoint
        ProgressService.set_progress(
            user_id,
            {
                "status": latest_job_data["status"],
                "total": latest_job_data["total"],
                "completed": latest_job_data["completed"],
                "failed": latest_job_data["failed"],
                "current_video": f"Added {latest_job_data['completed']} of {latest_job_data['total']} videos",
            },
        )

        api_logger.info(
            f"Playlist job {job_id}: Progress {latest_job_data['completed']}/{latest_job_data['total']} "
            f"({(latest_job_data['completed'] / latest_job_data['total'] * 100):.1f}%) - "
            f"{add_result['succeeded']} succeeded, {add_result['failed']} failed"
        )

    # Check if job is complete
    is_complete = latest_job_data and (
        latest_job_data.get("completed", 0) + latest_job_data.get("failed", 0)
        >= latest_job_data.get("total", 0)
    )

    if is_complete:
        # Mark job as completed
        final_job_data = get_playlist_job_data(job_id)
        if final_job_data:
            final_job_data["status"] = "completed"
            final_job_data["current_video"] = None
            set_playlist_job_data(job_id, final_job_data, expire=7200)

            # Update user progress to completed
            ProgressService.set_progress(
                user_id,
                {
                    "status": "completed",
                    "total": final_job_data["total"],
                    "completed": final_job_data["completed"],
                    "failed": final_job_data["failed"],
                    "current_video": None,
                },
            )

            api_logger.info(
                f"Playlist job {job_id} completed! {final_job_data['completed']} videos added successfully, "
                f"{final_job_data['failed']} failed."
            )

    return {
        "processed": len(video_youtube_ids),
        "complete": is_complete,
    }
