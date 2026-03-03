"""Taste profile service with k-means clustering and interest drift detection."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import List

import numpy as np
from openai import AsyncOpenAI
from pydantic import BaseModel
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_distances
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import api_logger
from app.redis_client import get_redis


# Structured output for LLM cluster labeling and profile generation
class ClusterLabel(BaseModel):
    """Label for a single cluster."""

    label: str
    description: str


class ClusterLabels(BaseModel):
    """Labels for all clusters."""

    labels: List[ClusterLabel]


class TasteProfileOutput(BaseModel):
    """LLM structured output for the full taste profile narrative."""

    identity_summary: str
    personality_tags: List[str]
    emerging_interest_labels: List[str]
    declining_interest_labels: List[str]
    content_depth: str
    viewing_pattern: str


PROFILE_CACHE_TTL = 86400  # 24 hours
PROFILE_CACHE_PREFIX = "taste_profile"
MIN_VIDEOS_FOR_PROFILE = 20


class ProfileService:
    """Service for generating content taste profiles with clustering and drift detection."""

    def __init__(self, user_id: int, db: Session):
        self.user_id = user_id
        self.db = db
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.redis = get_redis()

    def get_cached_profile(self) -> dict | None:
        """Get cached taste profile from Redis."""
        data = self.redis.get(f"{PROFILE_CACHE_PREFIX}:{self.user_id}")
        if data:
            return json.loads(data)
        return None

    def cache_profile(self, profile: dict) -> None:
        """Cache taste profile in Redis."""
        self.redis.set(
            f"{PROFILE_CACHE_PREFIX}:{self.user_id}",
            json.dumps(profile, default=str),
            expire=PROFILE_CACHE_TTL,
        )

    def get_video_count(self) -> int:
        """Get the count of user's videos with embeddings."""
        result = self.db.execute(
            text(
                "SELECT COUNT(*) FROM videos WHERE user_id = :user_id AND embedding IS NOT NULL"
            ),
            {"user_id": self.user_id},
        )
        return result.scalar() or 0

    def _fetch_embeddings_and_metadata(self) -> tuple[np.ndarray, list[dict]]:
        """Fetch all video embeddings and metadata for clustering."""
        result = self.db.execute(
            text(
                """
                SELECT
                    v.id, v.title, v.channel_title, v.duration_seconds,
                    v.liked_at, v.published_at,
                    v.embedding::text as embedding_text
                FROM videos v
                WHERE v.user_id = :user_id
                    AND v.embedding IS NOT NULL
                ORDER BY v.liked_at ASC
                """
            ),
            {"user_id": self.user_id},
        )

        embeddings = []
        metadata = []

        for row in result:
            # Parse pgvector embedding string "[0.1,0.2,...]" to numpy array
            embedding_str = row.embedding_text.strip("[]")
            embedding = np.array(
                [float(x) for x in embedding_str.split(",")], dtype=np.float32
            )
            embeddings.append(embedding)

            # Fetch categories and tags for this video
            cats = self.db.execute(
                text(
                    """
                    SELECT c.name FROM categories c
                    JOIN video_categories vc ON vc.category_id = c.id
                    WHERE vc.video_id = :video_id
                    """
                ),
                {"video_id": row.id},
            )
            tags = self.db.execute(
                text(
                    """
                    SELECT t.name FROM tags t
                    JOIN video_tags vt ON vt.tag_id = t.id
                    WHERE vt.video_id = :video_id
                    """
                ),
                {"video_id": row.id},
            )

            metadata.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "channel": row.channel_title,
                    "duration": row.duration_seconds,
                    "liked_at": row.liked_at,
                    "published_at": row.published_at,
                    "categories": [r.name for r in cats],
                    "tags": [r.name for r in tags],
                }
            )

        return np.array(embeddings), metadata

    def _find_optimal_k(self, embeddings: np.ndarray) -> int:
        """Find optimal number of clusters using silhouette score."""
        n_samples = len(embeddings)
        if n_samples < 4:
            return min(n_samples, 3)

        k_range = range(3, min(13, n_samples))
        best_k = 3
        best_score = -1

        for k in k_range:
            try:
                kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
                labels = kmeans.fit_predict(embeddings)
                score = silhouette_score(embeddings, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except Exception:
                continue

        return best_k

    def _cluster_videos(
        self, embeddings: np.ndarray, metadata: list[dict]
    ) -> list[dict]:
        """Run k-means clustering and identify representative videos per cluster."""
        k = self._find_optimal_k(embeddings)
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        clusters = []
        total = len(embeddings)

        for cluster_id in range(k):
            mask = labels == cluster_id
            cluster_indices = np.where(mask)[0]
            cluster_embeddings = embeddings[mask]
            centroid = kmeans.cluster_centers_[cluster_id]

            # Find 3 representative videos (closest to centroid)
            distances = cosine_distances([centroid], cluster_embeddings)[0]
            closest_indices = np.argsort(distances)[:3]
            representative_ids = [
                metadata[cluster_indices[i]]["id"] for i in closest_indices
            ]
            representative_titles = [
                metadata[cluster_indices[i]]["title"] for i in closest_indices
            ]

            # Aggregate categories and tags in cluster
            cluster_categories: dict[str, int] = defaultdict(int)
            cluster_tags: dict[str, int] = defaultdict(int)
            for idx in cluster_indices:
                for cat in metadata[idx].get("categories", []):
                    cluster_categories[cat] += 1
                for tag in metadata[idx].get("tags", []):
                    cluster_tags[tag] += 1

            top_categories = sorted(
                cluster_categories.items(), key=lambda x: x[1], reverse=True
            )[:3]
            top_tags = sorted(cluster_tags.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]

            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "size": int(np.sum(mask)),
                    "percentage": round(float(np.sum(mask)) / total * 100, 1),
                    "representative_ids": representative_ids,
                    "representative_titles": representative_titles,
                    "top_categories": [c[0] for c in top_categories],
                    "top_tags": [t[0] for t in top_tags],
                    "centroid": centroid,
                }
            )

        # Sort by size descending
        clusters.sort(key=lambda c: c["size"], reverse=True)
        return clusters

    def _detect_drift(self, embeddings: np.ndarray, metadata: list[dict]) -> list[dict]:
        """Detect interest drift by comparing quarterly embedding centroids."""
        # Group videos by quarter
        quarterly: dict[str, list[int]] = defaultdict(list)
        for i, meta in enumerate(metadata):
            if meta.get("liked_at"):
                dt = meta["liked_at"]
                if isinstance(dt, str):
                    dt = datetime.fromisoformat(dt)
                quarter = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
                quarterly[quarter].append(i)

        if len(quarterly) < 2:
            return []

        # Compute centroid per quarter
        sorted_quarters = sorted(quarterly.keys())
        quarter_centroids = {}
        for q in sorted_quarters:
            indices = quarterly[q]
            quarter_embeddings = embeddings[indices]
            quarter_centroids[q] = np.mean(quarter_embeddings, axis=0)

        # Compute cosine distance between consecutive quarters
        drift_events = []
        drift_threshold = 0.15  # Cosine distance threshold

        for i in range(len(sorted_quarters) - 1):
            q1 = sorted_quarters[i]
            q2 = sorted_quarters[i + 1]
            c1 = quarter_centroids[q1].reshape(1, -1)
            c2 = quarter_centroids[q2].reshape(1, -1)
            distance = float(cosine_distances(c1, c2)[0][0])

            if distance > drift_threshold:
                # Get representative videos from each quarter for evidence
                q1_indices = quarterly[q1]
                q2_indices = quarterly[q2]
                evidence_ids = [metadata[q1_indices[0]]["id"]]
                if len(q2_indices) > 0:
                    evidence_ids.append(metadata[q2_indices[0]]["id"])

                drift_events.append(
                    {
                        "period": f"{q1} \u2192 {q2}",
                        "magnitude": round(distance, 4),
                        "evidence_video_ids": evidence_ids,
                        "q1": q1,
                        "q2": q2,
                    }
                )

        return drift_events

    def _compute_consumption_style(self, metadata: list[dict]) -> dict:
        """Compute consumption style metrics."""
        durations = [m["duration"] for m in metadata if m.get("duration") is not None]
        channels = [m.get("channel") for m in metadata if m.get("channel")]

        # Duration preference
        avg_duration = sum(durations) / len(durations) if durations else 0
        if avg_duration < 600:
            duration_pref = "short-form"
        elif avg_duration < 1800:
            duration_pref = "medium"
        else:
            duration_pref = "long-form"

        # Channel diversity
        unique_channels = len(set(channels))
        total = len(channels) if channels else 1
        diversity_ratio = unique_channels / total
        if diversity_ratio > 0.7:
            channel_div = "diverse"
        elif diversity_ratio > 0.4:
            channel_div = "moderate"
        else:
            channel_div = "focused"

        return {
            "avg_duration_preference": duration_pref,
            "channel_diversity": channel_div,
        }

    async def _label_clusters_with_llm(self, clusters: list[dict]) -> list[dict]:
        """Use LLM to label each cluster based on representative videos."""
        cluster_info = []
        for c in clusters:
            cluster_info.append(
                f"Cluster ({c['percentage']}% of library): "
                f"Representative videos: {', '.join(c['representative_titles'][:3])}. "
                f"Top categories: {', '.join(c['top_categories'][:3])}. "
                f"Top tags: {', '.join(c['top_tags'][:5])}"
            )

        prompt = "Label each video cluster with a short, descriptive name (2-4 words) and a brief description:\n\n"
        prompt += "\n".join(f"{i + 1}. {info}" for i, info in enumerate(cluster_info))

        try:
            response = await self.client.responses.parse(
                model=settings.openai_model,
                instructions="You label content clusters. For each cluster, provide a short label (2-4 words) and a one-sentence description of the content theme.",
                input=prompt,
                text_format=ClusterLabels,
                max_output_tokens=2000,
                reasoning={"effort": "none"},
            )
            result = response.output_parsed
            return [
                {"label": cl.label, "description": cl.description}
                for cl in result.labels
            ]
        except Exception as e:
            api_logger.error(f"Cluster labeling failed: {e}")
            return [
                {
                    "label": f"Cluster {i + 1}",
                    "description": ", ".join(c["top_categories"][:2]),
                }
                for i, c in enumerate(clusters)
            ]

    async def _generate_narrative(
        self,
        clusters: list[dict],
        cluster_labels: list[dict],
        drift_events: list[dict],
        consumption: dict,
        total_videos: int,
    ) -> dict:
        """Use LLM to generate the identity narrative and personality tags."""
        # Build context
        cluster_summary = "\n".join(
            f"- {cluster_labels[i]['label']} ({c['percentage']}%): {cluster_labels[i]['description']}"
            for i, c in enumerate(clusters)
            if i < len(cluster_labels)
        )

        drift_summary = ""
        if drift_events:
            drift_summary = "Interest shifts detected:\n" + "\n".join(
                f"- {d['period']}: magnitude {d['magnitude']}" for d in drift_events
            )

        prompt = f"""Analyze this user's video library profile:

Total videos: {total_videos}
Duration preference: {consumption['avg_duration_preference']}
Channel diversity: {consumption['channel_diversity']}

Interest clusters:
{cluster_summary}

{drift_summary}

Generate:
1. A 2-3 sentence identity summary (who this person is as a viewer)
2. 3-5 personality tags (like "lifelong learner", "creative explorer", "tech enthusiast")
3. Which clusters are emerging (growing) interests
4. Which clusters are declining interests
5. A content depth assessment ("surface", "moderate", "deep-dive")
6. A viewing pattern description (1 sentence)"""

        try:
            response = await self.client.responses.parse(
                model=settings.openai_model,
                instructions="You are an insightful content analyst. Analyze viewing patterns to generate personality insights. Be specific and interesting, not generic.",
                input=prompt,
                text_format=TasteProfileOutput,
                max_output_tokens=2000,
                reasoning={"effort": "low"},
            )
            result = response.output_parsed
            return {
                "identity_summary": result.identity_summary,
                "personality_tags": result.personality_tags,
                "emerging_labels": result.emerging_interest_labels,
                "declining_labels": result.declining_interest_labels,
                "content_depth": result.content_depth,
                "viewing_pattern": result.viewing_pattern,
            }
        except Exception as e:
            api_logger.error(f"Narrative generation failed: {e}")
            return {
                "identity_summary": "Unable to generate profile narrative.",
                "personality_tags": [],
                "emerging_labels": [],
                "declining_labels": [],
                "content_depth": "moderate",
                "viewing_pattern": "Regular viewing pattern",
            }

    async def generate_profile(self) -> dict:
        """
        Generate a full taste profile.

        Steps:
        1. Fetch embeddings and metadata
        2. K-means clustering with auto k
        3. Temporal drift detection
        4. Consumption style analysis
        5. LLM labeling and narrative generation
        6. Assemble and cache the profile
        """
        video_count = self.get_video_count()
        if video_count < MIN_VIDEOS_FOR_PROFILE:
            return {
                "status": "not_available",
                "profile": None,
                "video_count": video_count,
                "min_videos_required": MIN_VIDEOS_FOR_PROFILE,
            }

        api_logger.info(
            f"Generating taste profile for user {self.user_id} ({video_count} videos)"
        )

        # 1. Fetch data
        embeddings, metadata = self._fetch_embeddings_and_metadata()

        if len(embeddings) < MIN_VIDEOS_FOR_PROFILE:
            return {
                "status": "not_available",
                "profile": None,
                "video_count": len(embeddings),
                "min_videos_required": MIN_VIDEOS_FOR_PROFILE,
            }

        # 2. Cluster
        clusters = self._cluster_videos(embeddings, metadata)

        # 3. Drift detection
        drift_events = self._detect_drift(embeddings, metadata)

        # 4. Consumption style
        consumption = self._compute_consumption_style(metadata)

        # 5. LLM labeling
        cluster_labels = await self._label_clusters_with_llm(clusters)

        # 6. Narrative
        narrative = await self._generate_narrative(
            clusters, cluster_labels, drift_events, consumption, len(embeddings)
        )

        # Classify clusters as primary, emerging, or declining
        primary_interests = []
        emerging_interests = []
        declining_interests = []

        for i, cluster in enumerate(clusters):
            if i >= len(cluster_labels):
                break

            interest = {
                "label": cluster_labels[i]["label"],
                "percentage": cluster["percentage"],
                "representative_video_ids": cluster["representative_ids"],
                "description": cluster_labels[i]["description"],
            }

            label = cluster_labels[i]["label"]
            if label in narrative.get("emerging_labels", []):
                emerging_interests.append(interest)
            elif label in narrative.get("declining_labels", []):
                declining_interests.append(interest)
            else:
                primary_interests.append(interest)

        # Build drift events with labels
        labeled_drift_events = []
        for event in drift_events:
            labeled_drift_events.append(
                {
                    "period": event["period"],
                    "from_interest": event.get("q1", "earlier"),
                    "to_interest": event.get("q2", "later"),
                    "magnitude": event["magnitude"],
                    "evidence_video_ids": event["evidence_video_ids"],
                }
            )

        profile = {
            "identity_summary": narrative["identity_summary"],
            "primary_interests": primary_interests,
            "emerging_interests": emerging_interests,
            "declining_interests": declining_interests,
            "consumption_style": {
                "avg_duration_preference": consumption["avg_duration_preference"],
                "channel_diversity": consumption["channel_diversity"],
                "content_depth": narrative.get("content_depth", "moderate"),
                "viewing_pattern": narrative.get(
                    "viewing_pattern", "Regular viewing pattern"
                ),
            },
            "drift_events": labeled_drift_events,
            "personality_tags": narrative.get("personality_tags", []),
        }

        result = {
            "status": "ready",
            "profile": profile,
            "video_count": len(embeddings),
            "min_videos_required": MIN_VIDEOS_FOR_PROFILE,
        }

        # Cache the profile
        self.cache_profile(result)

        api_logger.info(
            f"Taste profile generated for user {self.user_id}: "
            f"{len(primary_interests)} primary, {len(emerging_interests)} emerging, "
            f"{len(declining_interests)} declining interests"
        )

        return result
