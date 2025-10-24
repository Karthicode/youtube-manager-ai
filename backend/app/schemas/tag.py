from pydantic import BaseModel, ConfigDict


class TagBase(BaseModel):
    """Base tag schema."""

    name: str
    slug: str


class TagCreate(TagBase):
    """Schema for creating a tag."""

    pass


class TagResponse(TagBase):
    """Tag response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usage_count: int = 0


class TagUpdate(BaseModel):
    """Schema for updating tag."""

    name: str | None = None
