from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env."""

    app_name: str = "ParallelLines"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/parallellines"
    redis_url: str = "redis://localhost:6379/0"
    slow_request_ms: int = 500
    hot_rank_interval_seconds: int = 300

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5174", "http://127.0.0.1:5174"]
    )

    jwt_secret_key: str = "change-me-in-production-with-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
