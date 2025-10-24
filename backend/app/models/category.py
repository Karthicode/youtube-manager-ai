from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

# Many-to-many relationship between videos and categories
video_categories = Table(
    "video_categories",
    Base.metadata,
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base):
    """Category model for video categorization."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code

    # Relationships
    videos = relationship(
        "Video", secondary=video_categories, back_populates="categories"
    )
