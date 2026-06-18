from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env."""

    app_name: str = "ParallelLines"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "mysql+asyncmy://root:root@localhost:3306/parallellines?charset=utf8mb4"
    redis_url: str = "redis://localhost:6379/0"
    slow_request_ms: int = 500
    background_job_poll_seconds: int = 5
    background_job_batch_size: int = 25
    background_job_retry_delay_seconds: int = 60
    background_hot_rank_interval_seconds: int = 300
    background_upload_cleanup_interval_seconds: int = 3600
    background_session_cleanup_interval_seconds: int = 3600
    background_digest_interval_seconds: int = 3600
    background_frontier_news_interval_seconds: int = 3600
    frontier_news_board_slug: str = "frontier"
    frontier_news_bot_username: str = "小小资讯"
    frontier_news_bot_email: str = "frontier-news-bot@parallellines.local"
    frontier_news_ai_provider: str = "local"
    frontier_news_ai_model: str = "local-deterministic-v1"
    frontier_news_request_timeout_seconds: float = 15.0

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5174", "http://127.0.0.1:5174"]
    )

    jwt_secret_key: str = "change-me-in-production-with-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 360
    refresh_token_days: int = 30

    email_delivery_mode: Literal["memory", "smtp"] = "memory"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@parallellines.local"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 10.0
    email_webhook_secret: str | None = None
    email_verification_code_ttl_minutes: int = 5
    email_verification_resend_seconds: int = 60
    email_verification_max_attempts: int = 5
    password_reset_token_ttl_minutes: int = 5
    password_reset_code_max_attempts: int = 5
    email_change_token_ttl_minutes: int = 30
    two_factor_challenge_minutes: int = 5
    two_factor_issuer: str = "ParallelLines"
    oauth_enabled_providers: list[str] = Field(default_factory=list)
    rate_limit_window_seconds: int = 60
    rate_limit_register_ip: int = 5
    rate_limit_register_email: int = 3
    rate_limit_login_ip: int = 10
    rate_limit_login_account: int = 10
    rate_limit_topic_user: int = 5
    rate_limit_topic_ip: int = 10
    rate_limit_reply_user: int = 10
    rate_limit_reply_ip: int = 20
    rate_limit_upload_user: int = 20
    rate_limit_upload_ip: int = 30
    rate_limit_flag_user: int = 10
    rate_limit_flag_ip: int = 20
    new_user_link_limit: int = 5
    new_user_screening_days: int = 7

    upload_storage_backend: Literal["local", "s3"] = "local"
    upload_storage_path: str = "var/uploads"
    upload_cdn_base_url: str | None = None
    upload_s3_bucket: str | None = None
    upload_s3_region: str | None = None
    upload_s3_endpoint_url: str | None = None
    upload_s3_access_key_id: str | None = None
    upload_s3_secret_access_key: str | None = None
    upload_s3_request_timeout_seconds: float = 10.0
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_max_avatar_bytes: int = 2 * 1024 * 1024
    upload_max_files_per_post: int = 10
    upload_temporary_ttl_hours: int = 24
    backup_storage_path: str = "var/backups"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncmy", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
