"""Authentication service for JWT tokens and YouTube OAuth."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any

from jose import jwt
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User


class AuthService:
    """Service for handling authentication and authorization."""

    @staticmethod
    def create_access_token(data: Dict[str, Any]) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        to_encode.update({"exp": expire, "type": "access"})

        encoded_jwt = jwt.encode(
            to_encode, settings.secret_key, algorithm=settings.algorithm
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token.

        Args:
            data: Data to encode in the token

        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})

        encoded_jwt = jwt.encode(
            to_encode, settings.secret_key, algorithm=settings.algorithm
        )
        return encoded_jwt

    @staticmethod
    def create_tokens_for_user(user: User) -> Dict[str, str]:
        """
        Create both access and refresh tokens for a user.

        Args:
            user: User object

        Returns:
            Dictionary with access_token and refresh_token
        """
        token_data = {"sub": str(user.id)}

        access_token = AuthService.create_access_token(token_data)
        refresh_token = AuthService.create_refresh_token(token_data)

        return {"access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    def get_youtube_oauth_flow() -> Flow:
        """
        Create a Google OAuth Flow for YouTube authentication.

        Returns:
            Configured OAuth Flow object
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.youtube_client_id,
                    "client_secret": settings.youtube_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.youtube_scopes,
            redirect_uri=settings.youtube_redirect_uri,
        )

        return flow

    @staticmethod
    def get_youtube_authorization_url() -> str:
        """
        Generate YouTube OAuth authorization URL.

        Returns:
            Authorization URL string
        """
        flow = AuthService.get_youtube_oauth_flow()
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Force consent to get refresh token
        )

        return authorization_url

    @staticmethod
    def exchange_youtube_code_for_tokens(code: str) -> Credentials:
        """
        Exchange authorization code for OAuth tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Google OAuth credentials
        """
        flow = AuthService.get_youtube_oauth_flow()
        flow.fetch_token(code=code)

        return flow.credentials

    @staticmethod
    def get_or_create_user_from_youtube(
        db: Session, credentials: Credentials, youtube_user_info: Dict[str, Any]
    ) -> User:
        """
        Get existing user or create new one from YouTube credentials.

        Args:
            db: Database session
            credentials: Google OAuth credentials
            youtube_user_info: User info from YouTube API

        Returns:
            User object
        """
        # Extract user data
        youtube_id = youtube_user_info.get("id")
        google_user_info = AuthService.get_google_user_info(credentials)
        email = google_user_info.get("email") or youtube_user_info.get("email")
        name = (
            youtube_user_info.get("title")
            or google_user_info.get("name")
            or youtube_user_info.get("name")
        )
        picture_url = youtube_user_info.get("thumbnails", {}).get("default", {}).get(
            "url"
        ) or google_user_info.get("picture")
        fallback_email = f"{youtube_id}@youtube.user"

        # Check if user exists
        user = db.query(User).filter_by(youtube_id=youtube_id).first()

        if not user:
            # Create new user
            user = User(
                youtube_id=youtube_id,
                email=email or fallback_email,
                name=name,
                picture_url=picture_url,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=credentials.expiry if credentials.expiry else None,
            )
            db.add(user)
        else:
            # Update existing user's tokens and info
            user.access_token = credentials.token
            user.refresh_token = credentials.refresh_token
            user.token_expires_at = credentials.expiry if credentials.expiry else None
            user.name = name or user.name
            user.picture_url = picture_url or user.picture_url
            if email:
                user.email = email
            elif not user.email:
                user.email = fallback_email

        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def get_google_user_info(credentials: Credentials) -> Dict[str, Any]:
        """
        Fetch authenticated Google account profile info (email/name/picture).

        Returns:
            Dict with Google user profile fields, or empty dict if unavailable.
        """
        try:
            oauth2 = build(
                "oauth2",
                "v2",
                credentials=credentials,
                cache_discovery=False,
            )
            profile = oauth2.userinfo().get().execute()
            return profile if isinstance(profile, dict) else {}
        except Exception:
            return {}
