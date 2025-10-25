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
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini-2025-04-14"
    openai_max_tokens: int = (
        16384  # GPT-4.1 mini supports up to 1M tokens, using 16k for safety
    )
    openai_temperature: float = 0.3

    # CORS - Support multiple origins (comma-separated string or list)
    cors_origins: list[str] = ["http://localhost:3000"]

    # Frontend URL (for OAuth redirects)
    frontend_url: str = "http://localhost:3000"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # QStash (Upstash background jobs)
    qstash_url: str = "https://qstash.upstash.io/v2/publish"
    qstash_token: str = ""  # Optional, leave empty if not using QStash
    qstash_current_signing_key: str = ""  # For webhook verification
    qstash_next_signing_key: str = ""  # For webhook verification

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.environment == "local"


settings = Settings()
