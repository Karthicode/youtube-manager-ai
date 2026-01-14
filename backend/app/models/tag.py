from typing import TYPE_CHECKING, List
from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.video import Video

# Many-to-many relationship between videos and tags
video_tags = Table(
    "video_tags",
    Base.metadata,
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Tag(Base):
    """Tag model for video tagging."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    usage_count: Mapped[int] = mapped_column(default=0)  # Track popularity

    # Relationships
    videos: Mapped[List["Video"]] = relationship(
        secondary=video_tags, back_populates="tags"
    )
