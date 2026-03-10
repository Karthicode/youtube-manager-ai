"""User preferences router for auto-categorization settings."""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_preference import UserPreference
from app.schemas.preferences import UserPreferenceResponse, UserPreferenceUpdate
from app.logger import api_logger
from app.redis_client import get_redis
from app.utils.cache_invalidation import invalidate_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])

CACHE_TTL = 3600  # 60 minutes


@router.get("", response_model=UserPreferenceResponse)
def get_preferences(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> UserPreferenceResponse:
    """Get current user's preferences. Create defaults if not exists."""
    redis = get_redis()
    cache_key = f"preferences:{current_user.id}"
    cached = redis.get(cache_key)
    if cached:
        return UserPreferenceResponse.model_validate(json.loads(cached))

    # Check if user has preferences
    if not current_user.preference:
        # Create default preferences
        api_logger.info(f"Creating default preferences for user {current_user.id}")
        preference = UserPreference(
            user_id=current_user.id,
            auto_categorize_enabled=False,
            auto_categorize_max_videos=50,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)
        result = UserPreferenceResponse.model_validate(preference)
        redis.set(
            cache_key, json.dumps(result.model_dump(mode="json")), expire=CACHE_TTL
        )
        return result

    result = UserPreferenceResponse.model_validate(current_user.preference)
    redis.set(cache_key, json.dumps(result.model_dump(mode="json")), expire=CACHE_TTL)
    return result


@router.put("", response_model=UserPreferenceResponse)
def update_preferences(
    preferences: UserPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferenceResponse:
    """Update user preferences."""
    # Ensure user has preferences
    if not current_user.preference:
        # Create preferences first
        api_logger.info(f"Creating preferences for user {current_user.id}")
        preference = UserPreference(
            user_id=current_user.id,
            auto_categorize_enabled=False,
            auto_categorize_max_videos=50,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)
    else:
        preference = current_user.preference

    # Update fields if provided
    update_data = preferences.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(preference, field, value)

    preference.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(preference)

    invalidate_preferences(current_user.id)
    api_logger.info(f"Updated preferences for user {current_user.id}: {update_data}")
    return UserPreferenceResponse.model_validate(preference)
