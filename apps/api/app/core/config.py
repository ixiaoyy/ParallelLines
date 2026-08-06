from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env."""

    app_name: str = "ParallelLines"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    public_site_url: str | None = None
    web_app_shell_url: str | None = None

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
    background_living_forum_interval_seconds: int = 86400
    living_forum_publish_mode: Literal["auto", "review", "sample_review", "off"] = "auto"
    living_forum_daily_topic_limit: int = 1
    living_forum_daily_reply_limit: int = 0
    frontier_news_board_slug: str = "frontier"
    frontier_news_bot_username: str = "小小资讯"
    frontier_news_bot_email: str = "xiaoxiao-zixun@pingxingxian.space"
    frontier_news_ai_provider: str = "local"
    frontier_news_ai_model: str = "local-deterministic-v1"
    frontier_news_request_timeout_seconds: float = 15.0
    daily_report_ai_provider: Literal["opencode", "openai_compatible", "local"] = "opencode"
    daily_report_ai_model: str = "deepseek-v4-flash-free"
    daily_report_ai_base_url: str = "https://opencode.ai/zen"
    daily_report_ai_api_key: str = ""
    opencode_api_key: str = ""
    daily_report_ai_timeout_seconds: float = 30.0
    daily_report_ai_temperature: float = 0.8
    daily_report_ai_max_tokens: int = 1600
    pdf_translation_ai_model: str = "deepseek-v4-flash-free"
    pdf_translation_ai_base_url: str = "https://opencode.ai/zen"
    pdf_translation_ai_api_key: str = ""
    pdf_translation_ai_timeout_seconds: float = 90.0
    pdf_translation_ai_temperature: float = 0.1
    pdf_translation_ai_max_tokens: int = 8000
    pdf_translation_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
    )
    pdf_translation_max_pages: int = Field(default=30, ge=1, le=100)
    pdf_translation_render_dpi: int = Field(default=220, ge=150, le=300)
    pdf_translation_render_timeout_seconds: int = Field(default=120, ge=10, le=600)
    pdf_translation_ocr_timeout_seconds: int = Field(default=45, ge=5, le=180)
    pdf_translation_batch_chars: int = Field(default=6000, ge=1000, le=12000)
    pdf_translation_max_concurrency: int = Field(default=3, ge=1, le=5)
    pdf_translation_ocr_confidence: int = Field(default=55, ge=20, le=90)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ]
    )

    jwt_secret_key: str = "change-me-in-production-with-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 360
    refresh_token_days: int = 30

    # FableSpace SSO uses a one-time ticket plus a backend-only shared secret.
    fablespace_base_url: str = "http://127.0.0.1:3000"
    fablespace_sso_service_secret: str = ""
    fablespace_sso_ticket_ttl_seconds: int = 60

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
    rate_limit_daily_report_user: int = 12
    rate_limit_pdf_translation_user: int = 3
    new_user_link_limit: int = 5
    new_user_screening_days: int = 7

    upload_storage_backend: Literal["local", "s3"] = "local"
    upload_storage_path: str = "var/uploads"
    upload_cdn_base_url: str | None = None
    upload_public_cdn_urls: bool = False
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

    @field_validator("public_site_url")
    @classmethod
    def validate_public_site_url(cls, value: str | None) -> str | None:
        """Validate and normalize the configured canonical site origin.

        The optional ``value`` must be an absolute HTTP(S) origin without path,
        query, or fragment components. The normalized return value has no
        trailing slash; validation has no side effects.
        """

        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PUBLIC_SITE_URL must be an absolute HTTP(S) origin")
        return normalized

    @field_validator("web_app_shell_url")
    @classmethod
    def validate_web_app_shell_url(cls, value: str | None) -> str | None:
        """Validate the trusted internal URL used to load the compiled Web shell.

        The optional ``value`` may include an HTTP(S) path such as
        ``http://web/index.html``. The stripped URL is returned, and validation
        performs no network request or other side effect.
        """

        if value is None:
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.fragment:
            raise ValueError("WEB_APP_SHELL_URL must be an absolute HTTP(S) URL")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
