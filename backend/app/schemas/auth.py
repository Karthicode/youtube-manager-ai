from pydantic import BaseModel


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
