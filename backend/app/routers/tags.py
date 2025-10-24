"""Tags router for managing video tags."""

from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.tag import Tag
from app.models.video import Video
from app.schemas.tag import TagResponse

router = APIRouter(prefix="/tags")


@router.get("/", response_model=List[TagResponse])
async def get_tags(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None, description="Search tags by name"),
    limit: int | None = Query(
        None, ge=1, le=500, description="Limit number of results"
    ),
):
    """
    Get all tags for the current user with usage counts.

    Args:
        search: Optional search query to filter tags by name
        limit: Optional limit on number of tags returned

    Returns list of tags ordered by usage count (most used first).
    """
    # Query all tags
    query = db.query(Tag)

    # Apply search if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(Tag.name.ilike(search_term))

    tags = query.all()

    # For each tag, count videos for this user
    result = []
    for tag in tags:
        video_count = (
            db.query(func.count(Video.id))
            .join(Video.tags)
            .filter(Tag.id == tag.id)
            .filter(Video.user_id == current_user.id)
            .scalar()
        ) or 0

        result.append({
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "usage_count": video_count,
        })

    # Sort by usage count descending
    result.sort(key=lambda x: x["usage_count"], reverse=True)

    # Apply limit if provided
    if limit:
        result = result[:limit]

    return result


@router.get("/popular", response_model=List[TagResponse])
async def get_popular_tags(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 20,
):
    """
    Get most popular tags for the current user.

    Args:
        limit: Number of tags to return (default: 20)
    """
    popular_tags = (
        db.query(
            Tag,
            func.count(Video.id).label("video_count"),
        )
        .join(Video.tags)
        .filter(Video.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(func.count(Video.id).desc())
        .limit(limit)
        .all()
    )

    result = []
    for tag, count in popular_tags:
        tag_dict = {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "usage_count": count,
        }
        result.append(tag_dict)

    return result


@router.get("/cloud")
async def get_tag_cloud(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    min_count: int = Query(1, ge=1, description="Minimum usage count"),
    limit: int = Query(50, ge=1, le=200, description="Maximum tags to return"),
):
    """
    Get tag cloud data for visualization.

    Returns tags with their counts, suitable for rendering a tag cloud UI.

    Args:
        min_count: Minimum number of times a tag must be used to be included
        limit: Maximum number of tags to return
    """
    tags_data = (
        db.query(
            Tag.id,
            Tag.name,
            Tag.slug,
            func.count(Video.id).label("count"),
        )
        .join(Video.tags)
        .filter(Video.user_id == current_user.id)
        .group_by(Tag.id, Tag.name, Tag.slug)
        .having(func.count(Video.id) >= min_count)
        .order_by(func.count(Video.id).desc())
        .limit(limit)
        .all()
    )

    # Calculate relative sizes for visualization
    if tags_data:
        max_count = max(count for _, _, _, count in tags_data)
        min_found_count = min(count for _, _, _, count in tags_data)

        result = []
        for tag_id, name, slug, count in tags_data:
            # Normalize count to 1-5 scale for font sizes
            if max_count == min_found_count:
                size = 3
            else:
                size = 1 + int(
                    ((count - min_found_count) / (max_count - min_found_count)) * 4
                )

            result.append(
                {
                    "id": tag_id,
                    "name": name,
                    "slug": slug,
                    "count": count,
                    "size": size,  # 1-5 for CSS sizing
                }
            )

        return result

    return []
