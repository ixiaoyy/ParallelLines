from __future__ import annotations

from datetime import datetime
from typing import Literal

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

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

EmailDigestFrequency = Literal["off", "daily", "weekly"]
EmailDeliveryStatus = Literal["ok", "bounced", "complained", "disabled"]
EmailDeliveryEventType = Literal["sent", "delivered", "bounce", "complaint", "dropped"]
InboundEmailStatus = Literal["accepted", "unknown_sender", "topic_not_found", "recorded"]


class UserEmailPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_email_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_email_preferences_user"),
        Index("ix_user_email_preferences_digest", "digest_frequency", "last_digest_sent_at"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_replied: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_mentioned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_liked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_topic_new_post: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_board_new_topic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    digest_frequency: Mapped[str] = mapped_column(String(16), default="daily", nullable=False)
    last_digest_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(String(255))
    quiet_hours_start: Mapped[int | None] = mapped_column(
        Integer,
        comment="免打扰开始小时（UTC，0-23）；为空表示未启用免打扰。",
    )
    quiet_hours_end: Mapped[int | None] = mapped_column(
        Integer,
        comment="免打扰结束小时（UTC，0-23）；为空表示未启用免打扰；等于开始小时表示全天免打扰。",
    )

    user = relationship("User", lazy="selectin")


class EmailDeliveryEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_delivery_events"
    __table_args__ = (
        Index("ix_email_delivery_events_email_created", "email", "created_at"),
        Index("ix_email_delivery_events_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(64))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", lazy="selectin")


class InboundEmail(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inbound_emails"
    __table_args__ = (
        Index("ix_inbound_emails_status_created", "status", "created_at"),
        Index("ix_inbound_emails_topic_created", "topic_id", "created_at"),
    )

    from_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    raw_md: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", lazy="selectin")
    topic = relationship("Topic", lazy="selectin")
    post = relationship("Post", lazy="selectin")
