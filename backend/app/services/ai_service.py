"""AI service using OpenAI SDK for video categorization and tagging."""

import asyncio
from datetime import datetime
from typing import List

from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import api_logger
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag


# Pydantic models for OpenAI structured output
class VideoCategorization(BaseModel):
    """Structured output for video categorization."""

    primary_categories: List[str]  # 1-2 main categories
    secondary_categories: List[str] = []  # Optional additional categories
    tags: List[str]  # Exactly 5 most relevant tags
    confidence: float  # 0.0 to 1.0


class AIService:
    """Service for AI-powered video categorization using OpenAI."""

    # Predefined categories that AI can choose from
    AVAILABLE_CATEGORIES = [
        "Education",
        "Entertainment",
        "Music",
        "Gaming",
        "Technology",
        "Science",
        "Sports",
        "Lifestyle",
        "News",
        "DIY/How-to",
        "Comedy",
        "Documentary",
        "Food & Cooking",
        "Travel",
        "Health & Fitness",
        "Business",
        "Art & Design",
        "Fashion & Beauty",
        "Automotive",
        "Pets & Animals",
    ]

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.async_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def categorize_video(self, db: Session, video: Video) -> VideoCategorization:
        """
        Categorize a single video using OpenAI with structured output.

        Args:
            db: Database session
            video: Video object to categorize

        Returns:
            VideoCategorization with categories and tags
        """
        # Build prompt with video information
        prompt = self._build_categorization_prompt(video)

        # Call OpenAI API with structured output
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert video content analyzer. Your task is to categorize YouTube videos and generate relevant tags.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

Rules:
1. Choose 1-2 primary categories that best describe the video
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 most relevant and specific tags (no more, no less)
4. Tags should be lowercase, specific topics/concepts (e.g., "machine learning", "recipe", "tutorial")
5. Choose only the TOP 5 most important tags that best represent the video content
6. Assign a confidence score (0.0-1.0) based on how clear the video's content is
7. Use only categories from the available list""",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=VideoCategorization,
                max_completion_tokens=settings.openai_max_tokens,
            )

            result = completion.choices[0].message.parsed
            return result

        except Exception as e:
            import traceback

            api_logger.error(f"Error categorizing video {video.id}: {str(e)}")
            api_logger.debug(f"Full traceback: {traceback.format_exc()}")
            # Return default categorization on error
            return VideoCategorization(
                primary_categories=["Entertainment"],
                secondary_categories=[],
                tags=["video"],
                confidence=0.0,
            )

    def _build_categorization_prompt(self, video: Video) -> str:
        """Build prompt for video categorization."""
        duration_formatted = self._format_duration(video.duration_seconds)

        prompt_parts = [
            f"**Title:** {video.title}",
            f"**Channel:** {video.channel_title or 'Unknown'}",
            f"**Duration:** {duration_formatted}",
        ]

        if video.description:
            # Limit description length to avoid token limits
            description = (
                video.description[:500] + "..."
                if len(video.description) > 500
                else video.description
            )
            prompt_parts.append(f"**Description:** {description}")

        if video.view_count:
            prompt_parts.append(f"**Views:** {video.view_count:,}")

        if video.published_at:
            prompt_parts.append(f"**Published:** {video.published_at.year}")

        return "\n".join(prompt_parts)

    def _format_duration(self, seconds: int | None) -> str:
        """Format duration in seconds to human-readable format."""
        if not seconds:
            return "Unknown"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def apply_categorization(
        self, db: Session, video: Video, categorization: VideoCategorization
    ) -> Video:
        """
        Apply AI categorization results to a video.

        Args:
            db: Database session
            video: Video to update
            categorization: Categorization results from AI

        Returns:
            Updated video object
        """
        # Get or create categories
        all_category_names = (
            categorization.primary_categories + categorization.secondary_categories
        )

        video.categories.clear()
        for category_name in all_category_names:
            category = self._get_or_create_category(db, category_name)
            if category:
                video.categories.append(category)

        # Get or create tags - limit to top 5 most relevant
        video.tags.clear()
        # Ensure we only take the first 5 tags
        top_tags = categorization.tags[:5]
        for tag_name in top_tags:
            tag = self._get_or_create_tag(db, tag_name)
            if tag:
                video.tags.append(tag)
                tag.usage_count += 1

        # Mark as categorized
        video.is_categorized = True
        video.categorized_at = datetime.utcnow()

        db.commit()
        db.refresh(video)

        return video

    def _get_or_create_category(self, db: Session, name: str) -> Category | None:
        """Get existing category or create new one."""
        # Validate category is in allowed list
        if name not in self.AVAILABLE_CATEGORIES:
            return None

        slug = name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")

        category = db.query(Category).filter(Category.slug == slug).first()

        if not category:
            category = Category(
                name=name,
                slug=slug,
                description=f"Videos related to {name.lower()}",
            )
            db.add(category)
            db.flush()

        return category

    def _get_or_create_tag(self, db: Session, name: str) -> Tag:
        """Get existing tag or create new one."""
        slug = name.lower().replace(" ", "-")

        tag = db.query(Tag).filter(Tag.slug == slug).first()

        if not tag:
            tag = Tag(name=name.lower(), slug=slug, usage_count=0)
            db.add(tag)
            db.flush()

        return tag

    async def categorize_videos_batch_async(
        self, videos: List[Video]
    ) -> List[VideoCategorization]:
        """
        Categorize multiple videos in a single API call (much faster!).

        Args:
            videos: List of Video objects to categorize (up to 10 recommended)

        Returns:
            List of VideoCategorization results, one per video
        """
        if not videos:
            return []

        # Build batch prompt with all videos
        videos_info = []
        for i, video in enumerate(videos, 1):
            duration = self._format_duration(video.duration_seconds)
            desc = video.description[:200] if video.description else "No description"
            videos_info.append(
                f"{i}. **{video.title}** | {video.channel_title or 'Unknown'} | {duration}\n   {desc}"
            )

        batch_prompt = f"Categorize these {len(videos)} videos:\n\n" + "\n\n".join(
            videos_info
        )

        try:
            # Define batch response model
            class BatchCategorization(BaseModel):
                videos: List[VideoCategorization]

            completion = await self.async_client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert video content analyzer. Categorize ALL videos in the batch.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

For EACH video, provide:
1. Choose 1-2 primary categories
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 relevant tags
4. Assign confidence (0.0-1.0)

Return results in the SAME ORDER as input.""",
                    },
                    {"role": "user", "content": batch_prompt},
                ],
                response_format=BatchCategorization,
                max_completion_tokens=settings.openai_max_tokens,
            )

            result = completion.choices[0].message.parsed

            # Ensure we got results for all videos
            if len(result.videos) != len(videos):
                api_logger.warning(
                    f"Batch categorization returned {len(result.videos)} results for {len(videos)} videos"
                )
                # Pad with defaults if needed
                while len(result.videos) < len(videos):
                    result.videos.append(
                        VideoCategorization(
                            primary_categories=["Entertainment"],
                            tags=["video"],
                            confidence=0.0,
                        )
                    )

            return result.videos

        except Exception as e:
            api_logger.error(f"Error batch categorizing {len(videos)} videos: {str(e)}")
            # Return default categorizations
            return [
                VideoCategorization(
                    primary_categories=["Entertainment"],
                    tags=["video"],
                    confidence=0.0,
                )
                for _ in videos
            ]

    async def categorize_video_async(self, video: Video) -> VideoCategorization:
        """
        Async version of categorize_video for parallel batch processing.

        Uses AsyncOpenAI client for true async I/O.

        Args:
            video: Video object to categorize (no db needed for categorization)

        Returns:
            VideoCategorization with categories and tags
        """
        # Build prompt with video information
        prompt = self._build_categorization_prompt(video)

        # Call OpenAI API with structured output using async client
        try:
            completion = await self.async_client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert video content analyzer. Your task is to categorize YouTube videos and generate relevant tags.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

Rules:
1. Choose 1-2 primary categories that best describe the video
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 most relevant and specific tags (no more, no less)
4. Tags should be lowercase, specific topics/concepts (e.g., "machine learning", "recipe", "tutorial")
5. Choose only the TOP 5 most important tags that best represent the video content
6. Assign a confidence score (0.0-1.0) based on how clear the video's content is
7. Use only categories from the available list""",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=VideoCategorization,
                max_completion_tokens=settings.openai_max_tokens,
            )

            result = completion.choices[0].message.parsed
            return result

        except Exception as e:
            import traceback

            api_logger.error(f"Error categorizing video {video.id}: {str(e)}")
            api_logger.debug(f"Full traceback: {traceback.format_exc()}")
            # Return default categorization on error
            return VideoCategorization(
                primary_categories=["Entertainment"],
                secondary_categories=[],
                tags=["video"],
                confidence=0.0,
            )

    def batch_categorize_videos(
        self, db: Session, videos: List[Video], max_concurrent: int = 5
    ) -> int:
        """
        Categorize multiple videos in batch (synchronous version).

        Args:
            db: Database session
            videos: List of videos to categorize
            max_concurrent: Maximum concurrent API calls

        Returns:
            Number of successfully categorized videos
        """
        success_count = 0

        for video in videos:
            if video.is_categorized:
                continue

            try:
                categorization = self.categorize_video(db, video)
                self.apply_categorization(db, video, categorization)
                success_count += 1
            except Exception as e:
                api_logger.error(f"Failed to categorize video {video.id}: {str(e)}")
                continue

        return success_count

    async def batch_categorize_videos_async(
        self,
        db: Session,
        videos: List[Video],
        max_concurrent: int = 10,
        user_id: int | None = None,
    ) -> dict:
        """
        Categorize multiple videos in parallel using AsyncOpenAI with progress tracking.

        This is much faster than sequential processing for I/O-bound operations.

        Args:
            db: Database session
            videos: List of videos to categorize
            max_concurrent: Maximum concurrent API calls (default 10)
            user_id: Optional user ID for progress tracking

        Returns:
            Dictionary with success_count, failed_count, and results
        """
        from app.services.progress_service import ProgressService

        # Filter out already categorized videos
        uncategorized = [v for v in videos if not v.is_categorized]

        if not uncategorized:
            return {"success_count": 0, "failed_count": 0, "results": []}

        total_count = len(uncategorized)
        api_logger.info(
            f"Starting parallel categorization of {total_count} videos with concurrency={max_concurrent}"
        )

        # Initialize progress tracking
        if user_id:
            ProgressService.set_progress(
                user_id,
                {
                    "status": "in_progress",
                    "total": total_count,
                    "completed": 0,
                    "failed": 0,
                    "current_video": None,
                },
            )

        # Create semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(max_concurrent)
        completed_count = 0

        async def categorize_with_semaphore(video: Video):
            """Categorize a single video with rate limiting and progress tracking."""
            nonlocal completed_count
            async with semaphore:
                try:
                    # Update progress with current video
                    if user_id:
                        ProgressService.set_progress(
                            user_id,
                            {
                                "status": "in_progress",
                                "total": total_count,
                                "completed": completed_count,
                                "failed": 0,
                                "current_video": video.title[:50],
                            },
                        )

                    categorization = await self.categorize_video_async(video)
                    completed_count += 1

                    # Update progress after completion
                    if user_id:
                        ProgressService.set_progress(
                            user_id,
                            {
                                "status": "in_progress",
                                "total": total_count,
                                "completed": completed_count,
                                "failed": 0,
                                "current_video": None,
                            },
                        )

                    return (video, categorization, None)
                except Exception as e:
                    completed_count += 1
                    api_logger.error(f"Failed to categorize video {video.id}: {e}")
                    return (video, None, str(e))

        # Run all categorizations in parallel with rate limiting
        tasks = [categorize_with_semaphore(video) for video in uncategorized]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Apply categorizations to database
        success_count = 0
        failed_count = 0
        categorization_results = []

        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                api_logger.error(f"Exception during categorization: {result}")
                continue

            video, categorization, error = result

            if error:
                failed_count += 1
                categorization_results.append(
                    {"video_id": video.id, "success": False, "error": error}
                )
                continue

            try:
                # Apply categorization to video
                self.apply_categorization(db, video, categorization)
                success_count += 1
                categorization_results.append(
                    {
                        "video_id": video.id,
                        "success": True,
                        "categories": categorization.primary_categories
                        + categorization.secondary_categories,
                        "tags": categorization.tags,
                        "confidence": categorization.confidence,
                    }
                )
            except Exception as e:
                failed_count += 1
                api_logger.error(
                    f"Failed to apply categorization for video {video.id}: {e}"
                )
                categorization_results.append(
                    {"video_id": video.id, "success": False, "error": str(e)}
                )

        api_logger.info(
            f"Parallel categorization complete: {success_count} successful, {failed_count} failed"
        )

        # Clear progress on completion
        if user_id:
            ProgressService.clear_progress(user_id)

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "results": categorization_results,
        }
