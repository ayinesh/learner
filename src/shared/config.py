"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Anthropic
    anthropic_api_key: str

    # OpenAI (for embeddings)
    openai_api_key: str | None = None

    # Railway PostgreSQL
    database_url: str

    # Railway Redis
    redis_url: str = "redis://localhost:6379"

    # JWT Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_expiration_days: int = 7

    # Database Pool Settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # CORS Settings
    # In production, set CORS_ORIGINS to a comma-separated list of allowed origins
    # e.g., "https://app.example.com,https://www.example.com"
    cors_origins: str = ""

    # Application defaults
    default_session_minutes: int = 30
    max_session_minutes: int = 120
    min_session_minutes: int = 10

    # LLM Settings
    default_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7

    # Content Source API Keys (optional)
    twitter_bearer_token: str | None = None
    youtube_api_key: str | None = None
    github_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    # Feature Flags (can also be set via FF_* env vars)
    ff_use_database_persistence: bool = False
    ff_enable_nlp_commands: bool = False
    ff_enable_real_embeddings: bool = False
    ff_enable_background_jobs: bool = False

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list.

        Returns:
            List of allowed origins. In development, includes localhost.
            In production, only returns explicitly configured origins.
        """
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        # Default to localhost only in development
        if self.is_development:
            return [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ]
        # In production with no CORS_ORIGINS set, return empty list (no CORS allowed)
        return []


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
