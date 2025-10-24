"""AI service using OpenAI SDK for video categorization and tagging."""

from datetime import datetime
from typing import List

from openai import OpenAI
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

Available categories: {', '.join(self.AVAILABLE_CATEGORIES)}

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

    async def categorize_video_async(
        self, db: Session, video: Video
    ) -> VideoCategorization:
        """
        Async version of categorize_video for batch processing.

        This wraps the sync method - in production, use OpenAI's async client.
        """
        return self.categorize_video(db, video)

    def batch_categorize_videos(
        self, db: Session, videos: List[Video], max_concurrent: int = 5
    ) -> int:
        """
        Categorize multiple videos in batch.

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
