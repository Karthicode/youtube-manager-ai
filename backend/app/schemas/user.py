from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    name: str | None = None
    picture_url: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    youtube_id: str


class UserResponse(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    youtube_id: str
    created_at: datetime
    last_sync_at: datetime | None = None


class UserUpdate(BaseModel):
    """Schema for updating user."""

    name: str | None = None
    picture_url: str | None = None
