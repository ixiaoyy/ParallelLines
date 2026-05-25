from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type


class ApiKey(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_api_keys_token_hash"),
        Index("ix_api_keys_created_by", "created_by_id", "created_at"),
        Index("ix_api_keys_owner", "owner_user_id", "created_at"),
        Index("ix_api_keys_disabled", "disabled_at"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_type: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    note: Mapped[str | None] = mapped_column(String(500))


class WebhookEndpoint(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        Index("ix_webhook_endpoints_active", "active", "created_at"),
        Index("ix_webhook_endpoints_created_by", "created_by_id", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret: Mapped[str] = mapped_column(String(96), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    note: Mapped[str | None] = mapped_column(String(500))


class WebhookDelivery(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_created", "endpoint_id", "created_at"),
        Index("ix_webhook_deliveries_status_next", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_event_created", "event_type", "created_at"),
    )

    endpoint_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_body_excerpt: Mapped[str | None] = mapped_column(Text)

    endpoint: Mapped[WebhookEndpoint] = relationship("WebhookEndpoint", lazy="selectin")


class ExternalIntegration(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_integrations"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_external_integrations_provider"),
        Index("ix_external_integrations_enabled", "enabled", "updated_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class ExternalIntegrationEvent(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_integration_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_external_integration_event"),
        Index("ix_external_integration_events_provider_created", "provider", "created_at"),
        Index("ix_external_integration_events_status_next", "status", "next_retry_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    linked_resource_type: Mapped[str | None] = mapped_column(String(80))
    linked_resource_id: Mapped[str | None] = mapped_column(String(128))
    external_url: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str | None] = mapped_column(String(500))
