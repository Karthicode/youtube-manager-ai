"""Categories router for managing video categories."""

from typing import Annotated, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category
from app.models.video import Video
from app.schemas.category import CategoryResponse

router = APIRouter(prefix="/categories")


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get all available categories with video counts for the current user.

    Returns list of categories ordered by usage (most used first).
    """
    # Query all categories
    categories = db.query(Category).all()

    # For each category, count videos for this user
    result = []
    for category in categories:
        video_count = (
            db.query(func.count(Video.id))
            .join(Video.categories)
            .filter(Category.id == category.id)
            .filter(Video.user_id == current_user.id)
            .scalar()
        ) or 0

        result.append(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "color": category.color,
                "video_count": video_count,
            }
        )

    # Sort by video count descending
    result.sort(key=lambda x: x["video_count"], reverse=True)

    return result


@router.get("/popular", response_model=List[CategoryResponse])
async def get_popular_categories(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 10,
):
    """
    Get most popular categories for the current user.

    Args:
        limit: Number of categories to return (default: 10)
    """
    popular_categories = (
        db.query(
            Category,
            func.count(Video.id).label("video_count"),
        )
        .join(Video.categories)
        .filter(Video.user_id == current_user.id)
        .group_by(Category.id)
        .order_by(func.count(Video.id).desc())
        .limit(limit)
        .all()
    )

    result = []
    for category, count in popular_categories:
        category_dict = {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "color": category.color,
            "video_count": count,
        }
        result.append(category_dict)

    return result
