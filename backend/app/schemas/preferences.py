from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class UserPreferenceBase(BaseModel):
    """Base user preference schema."""

    auto_categorize_enabled: bool = False
    auto_categorize_max_videos: int = Field(default=50, ge=10, le=200)


class UserPreferenceCreate(UserPreferenceBase):
    """Schema for creating user preferences."""

    pass


class UserPreferenceUpdate(BaseModel):
    """Schema for updating user preferences."""

    auto_categorize_enabled: bool | None = None
    auto_categorize_max_videos: int | None = Field(default=None, ge=10, le=200)


class UserPreferenceResponse(UserPreferenceBase):
    """User preference response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
