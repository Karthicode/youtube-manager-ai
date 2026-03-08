from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(Base):
    """User preference model for storing auto-categorization and other settings."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Auto-categorization settings (OPT-IN by default)
    auto_categorize_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    auto_categorize_max_videos: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="preference")
