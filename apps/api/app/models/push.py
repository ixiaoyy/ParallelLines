from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin


class PushSubscription(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        Index("ix_push_subscriptions_user_enabled", "user_id", "enabled"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", lazy="selectin")
