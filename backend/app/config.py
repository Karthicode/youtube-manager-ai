import re

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Environment
    environment: str = "local"  # local, production

    # Application
    app_name: str = "YouTube Manager API"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/youtube_manager"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # YouTube API
    youtube_client_id: str
    youtube_client_secret: str
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/auth/youtube/callback"
    youtube_scopes: list[str] = [
        "openid",
        "https://www.googleapis.com/auth/youtube",  # Read & write access (for playlist creation)
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-5.2"
    openai_max_tokens: int = (
        16384  # GPT-5.2 supports up to 400K context, using 16k for safety
    )
    openai_temperature: float = 0.3

    # CORS - Support multiple origins (comma-separated string or list)
    cors_origins: list[str] = ["http://localhost:3000"]

    # Frontend URL (for OAuth redirects)
    frontend_url: str = "http://localhost:3000"

    # Regex allowlist for additional frontend origins allowed to complete
    # OAuth login and call the API (e.g. Vercel Preview Deployment URLs),
    # beyond `frontend_url` and localhost. Empty (default) disables preview
    # support: only frontend_url + localhost are allowed.
    #
    # No ^ or $ anchors here - spliced into a larger anchored pattern.
    # Must include the real Vercel team slug before enabling, otherwise any
    # Vercel user could stand up a lookalike deployment and pass the check.
    frontend_preview_origin_regex: str = ""

    # Backend API URL (for QStash worker callbacks)
    backend_url: str = "http://localhost:8000"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # QStash (Upstash background jobs)
    qstash_url: str = "https://qstash.upstash.io/v2/publish"
    qstash_token: str = ""  # Optional, leave empty if not using QStash
    qstash_current_signing_key: str = ""  # For webhook verification
    qstash_next_signing_key: str = ""  # For webhook verification
    qstash_queue_name: str = "categorize-videos"  # Queue name in QStash

    # Auto-categorization settings
    auto_categorize_enabled: bool = True  # Global kill switch
    auto_categorize_user_delay_seconds: int = 3  # Delay between users
    auto_categorize_cooldown_hours: int = 20  # Minimum hours between runs
    auto_categorize_sync_videos: int = (
        50  # Number of latest videos to sync before categorizing
    )

    @property
    def allowed_origin_regex(self) -> str:
        """Single regex for both CORS `allow_origin_regex` and OAuth
        `state`-origin validation, so the two allowlists can't drift apart.
        """
        parts = [re.escape(self.frontend_url), r"http://localhost:\d+"]
        if self.frontend_preview_origin_regex:
            parts.append(self.frontend_preview_origin_regex)
        return r"^(?:" + "|".join(parts) + r")$"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == "local"


settings = Settings()  # type: ignore[call-arg]
