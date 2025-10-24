from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    usage_count = Column(Integer, default=0, nullable=False)  # Track popularity

    # Relationships
    videos = relationship("Video", secondary=video_tags, back_populates="tags")
