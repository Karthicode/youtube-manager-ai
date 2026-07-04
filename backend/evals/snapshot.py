"""Copy one user's library from a SOURCE Postgres into the local eval DB.

Usage:
    poetry run python -m evals.snapshot --email user@example.com \
        [--source-url postgresql://...]

The source is explicit (flag or SNAPSHOT_SOURCE_URL) and only ever read.
The copied user is inert: OAuth tokens are stripped and the email is
rewritten to snapshot+<local-part>@example.com, so no tool can act on the
real YouTube account and the row cannot collide with a real login.
Idempotent: re-running replaces the snapshot user's videos with a fresh copy.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.category import Category
from app.models.tag import Tag
from app.models.user import User
from app.models.video import Video
from evals.db import create_schema, get_eval_session

# Every Video column except the PK and the FK we re-point at the eval user.
# Includes the pgvector `embedding` column, so no OpenAI calls are needed.
_VIDEO_COPY_COLUMNS = [
    c.name for c in Video.__table__.columns if c.name not in ("id", "user_id")
]


def _inert_user_copy(source_user: User) -> dict[str, Any]:
    """Kwargs for the eval-DB User row: tokens/keys stripped, email rewritten.

    `last_sync_at` is preserved — freshness-caveat cases depend on it.
    """
    local_part = source_user.email.split("@", 1)[0]
    return {
        "email": f"snapshot+{local_part}@example.com",
        "youtube_id": source_user.youtube_id,
        "name": source_user.name,
        "picture_url": source_user.picture_url,
        "access_token": None,
        "refresh_token": None,
        "token_expires_at": None,
        "api_key": None,
        "last_sync_at": source_user.last_sync_at,
        "last_auto_categorize_at": source_user.last_auto_categorize_at,
    }


def _get_or_create_category(
    target: Session, cache: dict[str, Category], src: Category
) -> Category:
    if src.name not in cache:
        cache[src.name] = target.query(Category).filter(
            Category.name == src.name
        ).first() or Category(
            name=src.name,
            slug=src.slug,
            description=src.description,
            color=src.color,
        )
        target.add(cache[src.name])
    return cache[src.name]


def _get_or_create_tag(target: Session, cache: dict[str, Tag], src: Tag) -> Tag:
    if src.name not in cache:
        cache[src.name] = target.query(Tag).filter(Tag.name == src.name).first() or Tag(
            name=src.name, slug=src.slug, usage_count=src.usage_count
        )
        target.add(cache[src.name])
    return cache[src.name]


def snapshot_user(source: Session, target: Session, email: str) -> tuple[int, int, int]:
    """Copy the user found by `email` from source into target (eval DB).

    Only SELECTs are issued against the source session. Returns
    (eval user id, video count, videos-with-embedding count).
    """
    source_user = source.query(User).filter(User.email == email).first()
    if source_user is None:
        raise SystemExit(f"No user with email {email!r} found in the source DB.")

    kwargs = _inert_user_copy(source_user)
    eval_user = target.query(User).filter(User.email == kwargs["email"]).first()
    if eval_user is None:
        eval_user = User(**kwargs)
        target.add(eval_user)
        target.flush()
    else:
        # Fresh snapshot each run: drop the old copy's videos (association
        # rows go with them via ON DELETE CASCADE) and refresh user fields.
        target.query(Video).filter(Video.user_id == eval_user.id).delete(
            synchronize_session=False
        )
        target.flush()
        for key, value in kwargs.items():
            setattr(eval_user, key, value)

    categories: dict[str, Category] = {}
    tags: dict[str, Tag] = {}
    copied = 0
    with_embeddings = 0
    for src_video in source.query(Video).filter(Video.user_id == source_user.id).all():
        video = Video(
            user_id=eval_user.id,
            **{name: getattr(src_video, name) for name in _VIDEO_COPY_COLUMNS},
        )
        for category in src_video.categories:
            video.categories.append(
                _get_or_create_category(target, categories, category)
            )
        for tag in src_video.tags:
            video.tags.append(_get_or_create_tag(target, tags, tag))
        target.add(video)
        copied += 1
        if src_video.embedding is not None:
            with_embeddings += 1

    target.commit()
    return eval_user.id, copied, with_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Source user's email")
    parser.add_argument(
        "--source-url",
        default=os.environ.get("SNAPSHOT_SOURCE_URL"),
        help="Source Postgres URL (defaults to env SNAPSHOT_SOURCE_URL)",
    )
    args = parser.parse_args()
    if not args.source_url:
        raise SystemExit(
            "No source DB: pass --source-url or set SNAPSHOT_SOURCE_URL. "
            "The source must be explicit — it never defaults to the app's "
            "own DATABASE_URL."
        )

    create_schema()
    source = sessionmaker(bind=create_engine(args.source_url))()
    target = get_eval_session()
    try:
        user_id, n_videos, n_embedded = snapshot_user(source, target, args.email)
        print(
            f"Snapshot complete: eval user id={user_id}, "
            f"{n_videos} videos ({n_embedded} with embeddings)"
        )
    finally:
        source.rollback()  # never write to the source
        source.close()
        target.close()


if __name__ == "__main__":
    main()
