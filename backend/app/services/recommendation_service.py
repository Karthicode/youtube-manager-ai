"""Channel recommendation service combining content-based and YouTube API approaches."""
from __future__ import annotations

from typing import List, Dict, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.services.youtube_service import YouTubeService
from app.logger import api_logger


class ChannelRecommendationService:
    """Service for generating personalized channel recommendations."""

    def __init__(self, user_id: int, db: Session, youtube_service: YouTubeService):
        """
        Initialize the recommendation service.

        Args:
            user_id: The user's ID
            db: Database session
            youtube_service: YouTube API service instance
        """
        self.user_id = user_id
        self.db = db
        self.youtube_service = youtube_service

    def get_user_preferences(self) -> Tuple[List[str], List[str], Set[str]]:
        """
        Analyze user's liked videos to extract preferences.

        Returns:
            Tuple of (top_categories, top_tags, existing_channel_ids)
        """
        # Get top 5 categories by video count
        top_categories_query = (
            self.db.query(Category.name, func.count(Video.id).label("count"))
            .join(Video.categories)
            .filter(Video.user_id == self.user_id)
            .group_by(Category.id, Category.name)
            .order_by(func.count(Video.id).desc())
            .limit(5)
            .all()
        )
        top_categories = [cat[0] for cat in top_categories_query]

        # Get top 10 tags by usage
        top_tags_query = (
            self.db.query(Tag.name, func.count(Video.id).label("count"))
            .join(Video.tags)
            .filter(Video.user_id == self.user_id)
            .group_by(Tag.id, Tag.name)
            .order_by(func.count(Video.id).desc())
            .limit(10)
            .all()
        )
        top_tags = [tag[0] for tag in top_tags_query]

        # Get all channel IDs user already has videos from
        existing_channels_query = (
            self.db.query(Video.channel_id)
            .filter(Video.user_id == self.user_id, Video.channel_id.isnot(None))
            .distinct()
            .all()
        )
        existing_channels = {row[0] for row in existing_channels_query}

        api_logger.debug(
            f"User preferences: {len(top_categories)} categories, "
            f"{len(top_tags)} tags, {len(existing_channels)} existing channels"
        )

        return top_categories, top_tags, existing_channels

    def content_based_recommendations(
        self,
        top_categories: List[str],
        top_tags: List[str],
        existing_channels: Set[str],
    ) -> List[Dict]:
        """
        Find channels through YouTube search based on user's content preferences.

        Args:
            top_categories: User's top categories
            top_tags: User's top tags
            existing_channels: Set of channel IDs user already has videos from

        Returns:
            List of candidate channel dicts with match info
        """
        candidates = []

        # Search by categories (top 3)
        for category in top_categories[:3]:
            try:
                results = self.youtube_service.search_channels_by_topic(
                    query=category, max_results=5
                )
                for channel in results:
                    if channel["id"] not in existing_channels:
                        candidates.append(
                            {
                                **channel,
                                "match_type": "category",
                                "match_value": category,
                            }
                        )
            except Exception as e:
                api_logger.warning(f"Search failed for category '{category}': {e}")

        # Search by tags (combine pairs of tags for better results)
        tag_queries = [
            " ".join(top_tags[i : i + 2]) for i in range(0, min(6, len(top_tags)), 2)
        ]
        for query in tag_queries:
            try:
                results = self.youtube_service.search_channels_by_topic(
                    query=query, max_results=3
                )
                for channel in results:
                    if channel["id"] not in existing_channels:
                        candidates.append(
                            {
                                **channel,
                                "match_type": "tag",
                                "match_value": query,
                            }
                        )
            except Exception as e:
                api_logger.warning(f"Search failed for tags '{query}': {e}")

        api_logger.debug(f"Found {len(candidates)} candidate channels")
        return candidates

    def score_and_deduplicate(
        self,
        candidates: List[Dict],
        top_categories: List[str],
        top_tags: List[str],
    ) -> List[Dict]:
        """
        Score candidates and remove duplicates.

        Scoring factors:
        - Category match: +0.3
        - Tag match: +0.2
        - Appearance count: +0.1 per appearance (max 0.3)
        - Subscriber tier bonus: +0.05 to +0.2

        Args:
            candidates: List of candidate channels
            top_categories: User's top categories
            top_tags: User's top tags

        Returns:
            Sorted list of unique channels with scores
        """
        channel_scores: Dict[str, Dict] = {}

        for candidate in candidates:
            channel_id = candidate["id"]

            if channel_id not in channel_scores:
                channel_scores[channel_id] = {
                    "channel": candidate,
                    "appearance_count": 0,
                    "category_matches": [],
                    "tag_matches": [],
                    "base_score": 0.0,
                }

            channel_scores[channel_id]["appearance_count"] += 1

            if candidate["match_type"] == "category":
                channel_scores[channel_id]["category_matches"].append(
                    candidate["match_value"]
                )
                channel_scores[channel_id]["base_score"] += 0.3
            else:
                channel_scores[channel_id]["tag_matches"].append(
                    candidate["match_value"]
                )
                channel_scores[channel_id]["base_score"] += 0.2

        # Calculate final scores and build results
        results = []
        for channel_id, data in channel_scores.items():
            # Appearance bonus (capped at 0.3)
            appearance_bonus = min(0.3, data["appearance_count"] * 0.1)

            # Generate recommendation reason
            reasons = []
            unique_categories = list(set(data["category_matches"]))
            unique_tags = list(set(data["tag_matches"]))

            if unique_categories:
                reasons.append(f"Creates content in {', '.join(unique_categories[:2])}")
            if unique_tags:
                reasons.append(f"Similar topics: {', '.join(unique_tags[:2])}")

            final_score = min(1.0, data["base_score"] + appearance_bonus)

            results.append(
                {
                    "channel_id": channel_id,
                    "channel_title": data["channel"].get("title", "Unknown"),
                    "thumbnail_url": data["channel"].get("thumbnail_url"),
                    "subscriber_count": None,  # Will be enriched later
                    "video_count": None,
                    "description": data["channel"].get("description"),
                    "recommendation_reason": (
                        ". ".join(reasons)
                        if reasons
                        else "Similar to channels you watch"
                    ),
                    "score": final_score,
                    "source": "content_based",
                }
            )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def enrich_with_details(
        self, recommendations: List[Dict], limit: int
    ) -> List[Dict]:
        """
        Fetch full channel details for top recommendations.

        Args:
            recommendations: List of recommendation dicts
            limit: Maximum number to enrich

        Returns:
            Enriched recommendations list
        """
        top_channel_ids = [r["channel_id"] for r in recommendations[:limit]]

        if not top_channel_ids:
            return recommendations[:limit]

        try:
            details = self.youtube_service.get_channel_details(top_channel_ids)
            details_map = {d["id"]: d for d in details}

            for rec in recommendations[:limit]:
                if rec["channel_id"] in details_map:
                    detail = details_map[rec["channel_id"]]
                    rec["thumbnail_url"] = detail.get("thumbnail_url")
                    rec["subscriber_count"] = detail.get("subscriber_count")
                    rec["video_count"] = detail.get("video_count")
                    rec["description"] = detail.get("description")

                    # Add subscriber tier bonus to score
                    sub_count = detail.get("subscriber_count") or 0
                    if sub_count > 1_000_000:
                        rec["score"] = min(1.0, rec["score"] + 0.15)
                    elif sub_count > 100_000:
                        rec["score"] = min(1.0, rec["score"] + 0.1)
                    elif sub_count > 10_000:
                        rec["score"] = min(1.0, rec["score"] + 0.05)

        except Exception as e:
            api_logger.warning(f"Failed to fetch channel details: {e}")

        # Re-sort after score adjustments
        recommendations[:limit] = sorted(
            recommendations[:limit], key=lambda x: x["score"], reverse=True
        )

        return recommendations[:limit]

    def get_recommendations(self, limit: int = 10) -> Dict:
        """
        Main entry point for getting channel recommendations.

        Args:
            limit: Maximum number of recommendations to return

        Returns:
            Dict with recommendations and analysis metadata
        """
        top_categories, top_tags, existing_channels = self.get_user_preferences()

        # Return empty if user has no preferences
        if not top_categories and not top_tags:
            api_logger.info(f"No preferences found for user {self.user_id}")
            return {
                "recommendations": [],
                "total_analyzed_channels": len(existing_channels),
                "top_categories": [],
                "top_tags": [],
            }

        # Get content-based candidates
        candidates = self.content_based_recommendations(
            top_categories, top_tags, existing_channels
        )

        if not candidates:
            api_logger.info(f"No candidates found for user {self.user_id}")
            return {
                "recommendations": [],
                "total_analyzed_channels": len(existing_channels),
                "top_categories": top_categories[:5],
                "top_tags": top_tags[:5],
            }

        # Score and deduplicate
        scored = self.score_and_deduplicate(candidates, top_categories, top_tags)

        # Enrich with full channel details
        enriched = self.enrich_with_details(scored, limit)

        api_logger.info(
            f"Generated {len(enriched)} recommendations for user {self.user_id}"
        )

        return {
            "recommendations": enriched,
            "total_analyzed_channels": len(existing_channels),
            "top_categories": top_categories[:5],
            "top_tags": top_tags[:5],
        }
