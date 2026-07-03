from datetime import datetime

from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    """Authenticated user profile.

    Field names match the frontend's User type and the payload the OAuth
    callback redirect encodes (picture, youtube_channel_id) — not the DB
    column names (picture_url, youtube_id).
    """

    id: int
    email: str
    name: str | None = None
    picture: str | None = None
    youtube_channel_id: str
    last_sync_at: datetime | None = None
    created_at: datetime


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    user_id: int


class YouTubeAuthURL(BaseModel):
    """YouTube OAuth authorization URL."""

    auth_url: str


class YouTubeCallback(BaseModel):
    """YouTube OAuth callback data."""

    code: str
    state: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class ApiKeyResponse(BaseModel):
    """API key response for MCP integration."""

    api_key: str | None
    mcp_endpoint: str
