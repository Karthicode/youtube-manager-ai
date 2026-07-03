"""Seed a small, known video library for golden-dataset evals.

Idempotent: running twice leaves one eval user with the same 15 videos.
The eval user's last_sync_at is fixed so freshness-caveat cases are stable.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.tag import Tag
from app.models.user import User
from app.models.video import Video
from app.services.embedding_service import EmbeddingService
from evals.db import create_schema, get_eval_session

EVAL_USER_EMAIL = "eval@example.com"
LAST_SYNC_AT = datetime(2026, 6, 20, tzinfo=timezone.utc)

# (title, channel, categories, tags, liked_at, duration_seconds)
VIDEOS = [
    (
        "Spicy Garlic Noodles in 15 Minutes",
        "Quick Eats",
        ["Food"],
        ["noodles", "recipe"],
        datetime(2026, 6, 18, tzinfo=timezone.utc),
        540,
    ),
    (
        "Ultimate Ramen Broth Guide",
        "Noodle Lab",
        ["Food"],
        ["ramen", "recipe"],
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        900,
    ),
    (
        "One-Pot Pasta for Busy Weeknights",
        "Quick Eats",
        ["Food"],
        ["pasta", "recipe"],
        datetime(2026, 5, 30, tzinfo=timezone.utc),
        480,
    ),
    (
        "No-Bake Mango Cheesecake",
        "Dessert Corner",
        ["Food"],
        ["dessert", "no-bake"],
        datetime(2026, 4, 10, tzinfo=timezone.utc),
        720,
    ),
    (
        "Sourdough Starter Day by Day",
        "Bread Basics",
        ["Food"],
        ["baking", "sourdough"],
        datetime(2026, 3, 2, tzinfo=timezone.utc),
        1100,
    ),
    (
        "Canon in D — Piano Cover",
        "Keys & Strings",
        ["Music"],
        ["piano", "classical"],
        datetime(2026, 6, 17, tzinfo=timezone.utc),
        210,
    ),
    (
        "Lofi Beats to Focus To",
        "Chill Radio",
        ["Music"],
        ["lofi", "focus"],
        datetime(2026, 5, 12, tzinfo=timezone.utc),
        3600,
    ),
    (
        "Tamil BGM Piano Medley",
        "Keys & Strings",
        ["Music"],
        ["piano", "bgm"],
        datetime(2026, 2, 20, tzinfo=timezone.utc),
        300,
    ),
    (
        "Nginx Explained in 10 Minutes",
        "DevOps Daily",
        ["Technology"],
        ["nginx", "devops"],
        datetime(2026, 6, 19, tzinfo=timezone.utc),
        600,
    ),
    (
        "PostgreSQL Indexing Deep Dive",
        "DB Internals",
        ["Technology"],
        ["postgres", "performance"],
        datetime(2026, 6, 1, tzinfo=timezone.utc),
        1500,
    ),
    (
        "Kubernetes for Small Projects",
        "DevOps Daily",
        ["Technology"],
        ["kubernetes", "devops"],
        datetime(2026, 4, 25, tzinfo=timezone.utc),
        1200,
    ),
    (
        "Rust Ownership Finally Explained",
        "Code Clarity",
        ["Technology"],
        ["rust", "programming"],
        datetime(2026, 3, 15, tzinfo=timezone.utc),
        840,
    ),
    (
        "How Rockets Steer in Space",
        "Orbital Mechanics",
        ["Education"],
        ["space", "physics"],
        datetime(2026, 5, 5, tzinfo=timezone.utc),
        660,
    ),
    (
        "The History of Tea Trade Routes",
        "Past Forward",
        ["Education"],
        ["history", "tea"],
        datetime(2026, 1, 8, tzinfo=timezone.utc),
        980,
    ),
    (
        "Interview: A Century of Indian Classical Music",
        "Past Forward",
        ["Education", "Music"],
        ["history", "music"],
        datetime(2025, 12, 1, tzinfo=timezone.utc),
        2400,
    ),
]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def seed(db: Session) -> int:
    """Create the eval user + library. Returns the eval user id."""
    user = db.query(User).filter(User.email == EVAL_USER_EMAIL).first()
    if user is not None:
        return user.id

    user = User(
        email=EVAL_USER_EMAIL,
        youtube_id="UC_EVAL_USER",
        name="Eval User",
        last_sync_at=LAST_SYNC_AT,
    )
    db.add(user)
    db.flush()

    cats: dict[str, Category] = {}
    tags: dict[str, Tag] = {}
    embedder = EmbeddingService()

    for title, channel, cat_names, tag_names, liked_at, duration in VIDEOS:
        video = Video(
            user_id=user.id,
            # youtube_id is String(20); "eval_" (5) + a 15-char slug fits exactly.
            youtube_id=f"eval_{_slug(title)[:15]}",
            title=title,
            channel_title=channel,
            liked_at=liked_at,
            duration_seconds=duration,
            is_categorized=True,
        )
        for name in cat_names:
            if name not in cats:
                cats[name] = db.query(Category).filter(
                    Category.name == name
                ).first() or Category(name=name, slug=_slug(name))
                db.add(cats[name])
            video.categories.append(cats[name])
        for name in tag_names:
            if name not in tags:
                tags[name] = db.query(Tag).filter(Tag.name == name).first() or Tag(
                    name=name, slug=_slug(name)
                )
                db.add(tags[name])
            video.tags.append(tags[name])
        db.add(video)
        db.flush()
        # Real embedding so search_videos (semantic) works in evals.
        asyncio.run(embedder.embed_video(db, video))

    db.commit()
    return user.id


if __name__ == "__main__":
    create_schema()
    session = get_eval_session()
    try:
        user_id = seed(session)
        count = session.query(Video).filter(Video.user_id == user_id).count()
        print(f"Seeded eval user id={user_id} with {count} videos")
    finally:
        session.close()
