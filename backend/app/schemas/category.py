from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    """Base category schema."""

    name: str
    slug: str
    description: str | None = None
    color: str | None = None


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""

    pass


class CategoryResponse(CategoryBase):
    """Category response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    video_count: int = 0


class CategoryUpdate(BaseModel):
    """Schema for updating category."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
