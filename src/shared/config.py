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

    # Railway PostgreSQL
    database_url: str

    # Railway Redis
    redis_url: str = "redis://localhost:6379"

    # JWT Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_expiration_days: int = 7

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
