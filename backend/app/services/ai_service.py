"""AI service using OpenAI SDK for video categorization and tagging."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import List

from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.config import settings
from app.logger import api_logger
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.redis_client import get_redis


# Pydantic models for OpenAI structured output
class VideoCategorization(BaseModel):
    """Structured output for video categorization."""

    primary_categories: List[str] = Field(min_length=1, max_length=2)
    secondary_categories: List[str] = Field(default_factory=list, max_length=2)
    tags: List[str] = Field(min_length=5, max_length=5)
    confidence: float  # 0.0 to 1.0


# Smart playlist structured output models
class SmartPlaylistVideoChoice(BaseModel):
    """LLM output for a single video selection."""

    video_id: int
    reason: str
    order_position: int


class SmartPlaylistOutput(BaseModel):
    """LLM structured output for smart playlist generation."""

    title: str
    description: str
    videos: List[SmartPlaylistVideoChoice]
    watching_order_rationale: str
    theme_summary: str


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

        # Call OpenAI API with structured output using the new Responses API
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=f"""You are an expert video content analyzer. Your task is to categorize YouTube videos and generate relevant tags.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

Rules:
1. Choose 1-2 primary categories that best describe the video
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 most relevant and specific tags (no more, no less)
4. Tags should be lowercase, specific topics/concepts (e.g., "machine learning", "recipe", "tutorial")
5. Choose only the TOP 5 most important tags that best represent the video content
6. Assign a confidence score (0.0-1.0) based on how clear the video's content is
7. Use only categories from the available list""",
                input=prompt,
                text_format=VideoCategorization,
                max_output_tokens=settings.openai_max_tokens,
            )

            result = response.output_parsed
            return result

        except Exception as e:
            api_logger.error(
                f"Error categorizing video {video.id}: {e}",
                exc_info=True,
            )
            raise

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
        video.categorized_at = datetime.now(timezone.utc)

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

            response = await self.async_client.responses.parse(
                model=self.model,
                instructions=f"""You are an expert video content analyzer. Categorize ALL videos in the batch.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

For EACH video, provide:
1. Choose 1-2 primary categories
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 relevant tags
4. Assign confidence (0.0-1.0)

Return results in the SAME ORDER as input.""",
                input=batch_prompt,
                text_format=BatchCategorization,
                max_output_tokens=settings.openai_max_tokens,
            )

            result = response.output_parsed

            # Ensure we got results for all videos
            if len(result.videos) != len(videos):
                raise ValueError(
                    "Batch categorization result count mismatch: "
                    f"got {len(result.videos)} results for {len(videos)} videos"
                )

            return result.videos

        except Exception as e:
            api_logger.error(
                f"Error batch categorizing {len(videos)} videos: {e}",
                exc_info=True,
            )
            raise

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

        # Call OpenAI API with structured output using async client and Responses API
        try:
            response = await self.async_client.responses.parse(
                model=self.model,
                instructions=f"""You are an expert video content analyzer. Your task is to categorize YouTube videos and generate relevant tags.

Available categories: {", ".join(self.AVAILABLE_CATEGORIES)}

Rules:
1. Choose 1-2 primary categories that best describe the video
2. Optionally add 0-2 secondary categories
3. Generate EXACTLY 5 most relevant and specific tags (no more, no less)
4. Tags should be lowercase, specific topics/concepts (e.g., "machine learning", "recipe", "tutorial")
5. Choose only the TOP 5 most important tags that best represent the video content
6. Assign a confidence score (0.0-1.0) based on how clear the video's content is
7. Use only categories from the available list""",
                input=prompt,
                text_format=VideoCategorization,
                max_output_tokens=settings.openai_max_tokens,
            )

            result = response.output_parsed
            return result

        except Exception as e:
            api_logger.error(
                f"Error categorizing video {video.id}: {e}",
                exc_info=True,
            )
            raise

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
            if isinstance(result, BaseException):
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

    async def generate_smart_playlist(
        self,
        description: str,
        user_id: int,
        max_videos: int,
        db: Session,
        refinement: str | None = None,
        previous_video_ids: list[int] | None = None,
    ) -> dict:
        """
        Generate a smart playlist from a natural language description.

        Uses hybrid retrieval: vector similarity + category/tag matching.
        Then asks the LLM to curate the final selection with reasons.

        Args:
            description: Natural language playlist description
            user_id: User ID
            max_videos: Maximum videos to include
            db: Database session
            refinement: Optional refinement to previous suggestion
            previous_video_ids: Video IDs from previous suggestion (for refinement)

        Returns:
            Dict with suggestion data and suggestion_id for caching
        """
        from app.services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()

        # 1. Retrieve candidates via semantic search (top 50)
        semantic_candidates = await embedding_service.search_similar_videos(
            db=db,
            query=description,
            user_id=user_id,
            limit=50,
            similarity_threshold=0.2,
        )

        # 2. Retrieve candidates via category/tag matching
        #    Infer likely categories from description using keyword matching
        category_candidates = self._get_category_matched_videos(
            db, description, user_id, limit=30
        )

        # 3. Merge and deduplicate
        seen_ids: set[int] = set()
        merged_candidates: list[dict] = []

        for video in semantic_candidates:
            if video["id"] not in seen_ids:
                seen_ids.add(video["id"])
                video["source"] = "semantic"
                merged_candidates.append(video)

        for video in category_candidates:
            if video["id"] not in seen_ids:
                seen_ids.add(video["id"])
                video["source"] = "category_match"
                merged_candidates.append(video)

        if not merged_candidates:
            return {
                "suggestion_id": "",
                "title": "",
                "description": "",
                "videos": [],
                "watching_order_rationale": "No matching videos found in your library.",
                "theme_summary": "",
            }

        # 4. Build candidate info for LLM
        candidate_info = []
        for v in merged_candidates[:80]:  # Cap at 80 to stay within token limits
            duration_str = self._format_duration(v.get("duration_seconds"))
            cats = ", ".join(c["name"] for c in v.get("categories", []))
            tags = ", ".join(t["name"] for t in v.get("tags", []))
            candidate_info.append(
                f"ID:{v['id']} | {v['title']} | {v.get('channel_title', 'Unknown')} | "
                f"{duration_str} | Categories: {cats or 'None'} | Tags: {tags or 'None'}"
            )

        candidates_text = "\n".join(candidate_info)

        # 5. Build prompt
        prompt = f"""User's playlist request: "{description}"

Available videos from their library (select up to {max_videos}):
{candidates_text}"""

        if refinement and previous_video_ids:
            prompt += f'\n\nPrevious selection IDs: {previous_video_ids}\nUser\'s refinement request: "{refinement}"\nAdjust the selection based on the refinement.'

        instructions = f"""You are a smart playlist curator. Given a user's playlist description and their video library, select the best matching videos and arrange them in an optimal watch order.

Rules:
1. Select up to {max_videos} videos that best match the playlist description
2. For each video, provide a brief reason why it fits the playlist
3. Arrange videos in a logical watch order (e.g., beginner to advanced, or thematic flow)
4. Generate a catchy playlist title and description
5. Provide a rationale for the watching order
6. Summarize the overall theme
7. Use the video ID numbers exactly as provided
8. Only select videos from the provided list"""

        try:
            response = await self.async_client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=prompt,
                text_format=SmartPlaylistOutput,
                max_output_tokens=settings.openai_max_tokens,
                reasoning={"effort": "low"},
            )

            result = response.output_parsed

            # 6. Cache the suggestion in Redis
            suggestion_id = str(uuid.uuid4())
            redis_client = get_redis()

            suggestion_data = {
                "suggestion_id": suggestion_id,
                "title": result.title,
                "description": result.description,
                "videos": [v.model_dump() for v in result.videos],
                "watching_order_rationale": result.watching_order_rationale,
                "theme_summary": result.theme_summary,
                "user_id": user_id,
            }

            redis_client.set(
                f"smart_playlist:{suggestion_id}",
                json.dumps(suggestion_data, default=str),
                expire=600,  # 10 min TTL
            )

            return suggestion_data

        except Exception as e:
            api_logger.error(f"Smart playlist generation failed: {e}", exc_info=True)
            raise

    def _get_category_matched_videos(
        self, db: Session, description: str, user_id: int, limit: int = 30
    ) -> list[dict]:
        """
        Find videos matching categories/tags inferred from the description.

        Uses keyword matching against category names and tag names.
        """
        description_lower = description.lower()

        # Find matching categories
        matching_categories = (
            db.query(Category)
            .filter(
                func.lower(Category.name).in_(
                    [
                        cat.lower()
                        for cat in self.AVAILABLE_CATEGORIES
                        if cat.lower() in description_lower
                    ]
                )
            )
            .all()
        )

        # Find matching tags
        matching_tags = (
            db.query(Tag)
            .filter(func.lower(Tag.name).op("LIKE")(f"%{description_lower[:50]}%"))
            .limit(10)
            .all()
        )

        if not matching_categories and not matching_tags:
            return []

        # Build query
        query = db.query(Video).filter(Video.user_id == user_id)

        conditions = []
        if matching_categories:
            cat_ids = [c.id for c in matching_categories]
            conditions.append(Video.categories.any(Category.id.in_(cat_ids)))
        if matching_tags:
            tag_ids = [t.id for t in matching_tags]
            conditions.append(Video.tags.any(Tag.id.in_(tag_ids)))

        query = query.filter(or_(*conditions))
        videos = query.limit(limit).all()

        # Convert to dicts
        result = []
        for v in videos:
            result.append(
                {
                    "id": v.id,
                    "youtube_id": v.youtube_id,
                    "title": v.title,
                    "description": v.description,
                    "thumbnail_url": v.thumbnail_url,
                    "channel_title": v.channel_title,
                    "channel_id": v.channel_id,
                    "duration_seconds": v.duration_seconds,
                    "published_at": v.published_at,
                    "view_count": v.view_count,
                    "like_count": v.like_count,
                    "is_categorized": v.is_categorized,
                    "categorized_at": v.categorized_at,
                    "liked_at": v.liked_at,
                    "created_at": v.created_at,
                    "user_id": v.user_id,
                    "categories": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "slug": c.slug,
                            "description": c.description,
                            "color": c.color,
                        }
                        for c in v.categories
                    ],
                    "tags": [
                        {
                            "id": t.id,
                            "name": t.name,
                            "slug": t.slug,
                            "usage_count": t.usage_count,
                        }
                        for t in v.tags
                    ],
                }
            )

        return result
