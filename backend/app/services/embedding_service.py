"""Embedding service for semantic search using OpenAI embeddings."""

from __future__ import annotations

import asyncio
from typing import List

from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.logger import api_logger
from app.models.video import Video


class EmbeddingService:
    """Service for generating and searching video embeddings."""

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _format_embedding_for_pgvector(self, embedding: List[float]) -> str:
        """
        Format embedding list for pgvector.

        pgvector expects format: '[0.1,0.2,0.3]' without spaces.
        """
        return "[" + ",".join(str(x) for x in embedding) + "]"

    def _build_embedding_text(self, video: Video) -> str:
        """
        Build text to embed for a video.

        Combines title, description, channel, and tags for richer context.
        """
        parts = [video.title]

        if video.channel_title:
            parts.append(f"Channel: {video.channel_title}")

        if video.description:
            # Limit description to avoid token limits
            desc = video.description[:500]
            parts.append(desc)

        # Add categories if available
        if video.categories:
            category_names = [c.name for c in video.categories]
            parts.append(f"Categories: {', '.join(category_names)}")

        # Add tags if available
        if video.tags:
            tag_names = [t.name for t in video.tags]
            parts.append(f"Tags: {', '.join(tag_names)}")

        return " | ".join(parts)

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a text string.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = await self.client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    async def embed_video(self, db: Session, video: Video) -> tuple[bool, str | None]:
        """
        Generate and store embedding for a single video.

        Args:
            db: Database session
            video: Video to embed

        Returns:
            Tuple of (success, error_message)
        """
        try:
            embedding_text = self._build_embedding_text(video)
            embedding = await self.generate_embedding(embedding_text)

            # Update video with embedding using raw SQL for pgvector
            embedding_str = self._format_embedding_for_pgvector(embedding)
            db.execute(
                text("UPDATE videos SET embedding = :embedding WHERE id = :id"),
                {"embedding": embedding_str, "id": video.id},
            )
            db.commit()

            return True, None
        except Exception as e:
            error_msg = str(e)
            api_logger.error(f"Failed to embed video {video.id}: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            return False, error_msg

    async def embed_videos_batch(
        self,
        db: Session,
        videos: List[Video],
        max_concurrent: int = 10,
    ) -> dict:
        """
        Generate embeddings for multiple videos in parallel.

        Args:
            db: Database session
            videos: List of videos to embed
            max_concurrent: Maximum concurrent API calls

        Returns:
            Dict with success_count and failed_count
        """
        if not videos:
            return {"success_count": 0, "failed_count": 0}

        # Filter videos that don't have embeddings yet
        videos_to_embed = [v for v in videos if v.embedding is None]

        if not videos_to_embed:
            return {"success_count": 0, "failed_count": 0, "skipped": len(videos)}

        api_logger.info(f"Generating embeddings for {len(videos_to_embed)} videos")

        semaphore = asyncio.Semaphore(max_concurrent)
        success_count = 0
        failed_count = 0

        async def embed_with_semaphore(video: Video) -> bool:
            async with semaphore:
                return await self.embed_video(db, video)

        tasks = [embed_with_semaphore(video) for video in videos_to_embed]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, bool) and result:
                success_count += 1
            else:
                failed_count += 1

        api_logger.info(
            f"Embedding complete: {success_count} successful, {failed_count} failed"
        )

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(videos_to_embed),
        }

    async def search_similar_videos(
        self,
        db: Session,
        query: str,
        user_id: int,
        limit: int = 20,
        similarity_threshold: float = 0.3,
    ) -> List[dict]:
        """
        Search for videos similar to a query using cosine similarity.

        Args:
            db: Database session
            query: Search query text
            user_id: User ID to filter videos
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of dicts with video data and similarity score
        """
        # Generate embedding for the query
        query_embedding = await self.generate_embedding(query)
        query_embedding_str = self._format_embedding_for_pgvector(query_embedding)

        # Search using cosine similarity
        # pgvector uses <=> for cosine distance (1 - similarity)
        # So we convert: similarity = 1 - distance
        # Use CAST() instead of :: to avoid SQLAlchemy parameter parsing issues
        result = db.execute(
            text(
                """
                SELECT
                    v.id,
                    v.youtube_id,
                    v.title,
                    v.description,
                    v.thumbnail_url,
                    v.channel_title,
                    v.channel_id,
                    v.duration_seconds,
                    v.published_at,
                    v.view_count,
                    v.like_count,
                    v.is_categorized,
                    v.categorized_at,
                    v.liked_at,
                    v.created_at,
                    v.user_id,
                    1 - (v.embedding <=> CAST(:query_embedding AS vector)) as similarity
                FROM videos v
                WHERE v.user_id = :user_id
                    AND v.embedding IS NOT NULL
                    AND 1 - (v.embedding <=> CAST(:query_embedding AS vector)) > :threshold
                ORDER BY v.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
                """
            ),
            {
                "query_embedding": query_embedding_str,
                "user_id": user_id,
                "threshold": similarity_threshold,
                "limit": limit,
            },
        )

        videos = []
        for row in result:
            video_dict = {
                "id": row.id,
                "youtube_id": row.youtube_id,
                "title": row.title,
                "description": row.description,
                "thumbnail_url": row.thumbnail_url,
                "channel_title": row.channel_title,
                "channel_id": row.channel_id,
                "duration_seconds": row.duration_seconds,
                "published_at": row.published_at,
                "view_count": row.view_count,
                "like_count": row.like_count,
                "is_categorized": row.is_categorized,
                "categorized_at": row.categorized_at,
                "liked_at": row.liked_at,
                "created_at": row.created_at,
                "user_id": row.user_id,
                "similarity": round(row.similarity, 4),
                "categories": [],
                "tags": [],
            }
            videos.append(video_dict)

        # Fetch categories and tags for the videos
        if videos:
            video_ids = [v["id"] for v in videos]

            # Fetch categories
            categories_result = db.execute(
                text(
                    """
                    SELECT vc.video_id, c.id, c.name, c.slug, c.description, c.color, c.icon
                    FROM video_categories vc
                    JOIN categories c ON c.id = vc.category_id
                    WHERE vc.video_id = ANY(:video_ids)
                    """
                ),
                {"video_ids": video_ids},
            )

            video_categories_map: dict = {vid: [] for vid in video_ids}
            for row in categories_result:
                video_categories_map[row.video_id].append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "slug": row.slug,
                        "description": row.description,
                        "color": row.color,
                        "icon": row.icon,
                    }
                )

            # Fetch tags
            tags_result = db.execute(
                text(
                    """
                    SELECT vt.video_id, t.id, t.name, t.slug, t.usage_count
                    FROM video_tags vt
                    JOIN tags t ON t.id = vt.tag_id
                    WHERE vt.video_id = ANY(:video_ids)
                    """
                ),
                {"video_ids": video_ids},
            )

            video_tags_map: dict = {vid: [] for vid in video_ids}
            for row in tags_result:
                video_tags_map[row.video_id].append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "slug": row.slug,
                        "usage_count": row.usage_count,
                    }
                )

            # Attach categories and tags to videos
            for video in videos:
                video["categories"] = video_categories_map.get(video["id"], [])
                video["tags"] = video_tags_map.get(video["id"], [])

        return videos

    def get_embedding_stats(self, db: Session, user_id: int) -> dict:
        """
        Get statistics about embeddings for a user's videos.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with total, embedded, and not_embedded counts
        """
        result = db.execute(
            text(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(embedding) as embedded,
                    COUNT(*) - COUNT(embedding) as not_embedded
                FROM videos
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )

        row = result.fetchone()
        if row is None:
            return {"total": 0, "embedded": 0, "not_embedded": 0}
        return {
            "total": row.total,
            "embedded": row.embedded,
            "not_embedded": row.not_embedded,
        }
