"""Authentication router for YouTube OAuth and JWT tokens."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import Token, YouTubeAuthURL
from app.services.auth_service import AuthService
from app.services.youtube_service import YouTubeService

router = APIRouter(prefix="/auth")


@router.get("/youtube/login", response_model=YouTubeAuthURL)
async def youtube_login():
    """
    Initiate YouTube OAuth flow.

    Returns authorization URL for user to grant permissions.
    """
    auth_url = AuthService.get_youtube_authorization_url()
    return YouTubeAuthURL(auth_url=auth_url)


@router.get("/youtube/callback")
async def youtube_callback(
    code: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Handle YouTube OAuth callback.

    Exchanges authorization code for tokens and creates/updates user.
    Returns JWT tokens for API authentication.
    """
    try:
        # Exchange code for credentials
        credentials = AuthService.exchange_youtube_code_for_tokens(code)

        # Get user info from YouTube
        youtube_service = YouTubeService.__new__(YouTubeService)
        youtube_service.user = type(
            "User",
            (),
            {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
            },
        )()
        youtube_service._initialize_client()

        youtube_user_info = youtube_service.get_user_info()

        if not youtube_user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not fetch user information from YouTube",
            )

        # Get or create user
        user = AuthService.get_or_create_user_from_youtube(
            db, credentials, youtube_user_info
        )

        # Generate JWT tokens
        tokens = AuthService.create_tokens_for_user(user)

        # Redirect to frontend with tokens
        from fastapi.responses import RedirectResponse
        from app.config import settings
        import urllib.parse
        import json

        # Encode user data
        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture_url,
            "youtube_channel_id": user.youtube_id,
            "last_sync_at": (
                user.last_sync_at.isoformat() if user.last_sync_at else None
            ),
        }

        # Build redirect URL with tokens using configured frontend URL
        frontend_callback_url = f"{settings.frontend_url}/auth/callback"
        params = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "user": urllib.parse.quote(json.dumps(user_data)),
        }

        redirect_url = f"{frontend_callback_url}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}",
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Refresh access token using refresh token.

    Args:
        refresh_token: Valid refresh token

    Returns:
        New access and refresh tokens
    """
    from jose import jwt, JWTError
    from app.config import settings
    from app.models.user import User

    try:
        # Decode refresh token
        payload = jwt.decode(
            refresh_token, settings.secret_key, algorithms=[settings.algorithm]
        )

        user_id: int = int(payload.get("sub"))
        token_type: str = payload.get("type")

        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Generate new tokens
        tokens = AuthService.create_tokens_for_user(user)

        return Token(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
