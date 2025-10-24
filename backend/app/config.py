from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

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
    openai_model: str = "gpt-5-mini"
    openai_max_tokens: int = 16384  # GPT-5 mini supports up to 128k, using 16k for safety

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100


settings = Settings()
