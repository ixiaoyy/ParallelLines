from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type


class BadgeDefinition(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "badge_definitions"
    __table_args__ = (UniqueConstraint("slug", name="uq_badge_definitions_slug"),)

    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    icon: Mapped[str] = mapped_column(String(24), nullable=False)
    trust_level_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserBadge(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_user_badges_idempotency_key"),
        Index("ix_user_badges_user_active", "user_id", "revoked_at"),
        Index("ix_user_badges_badge_created", "badge_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("badge_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(96))
    granted_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))

    badge: Mapped[BadgeDefinition] = relationship("BadgeDefinition", lazy="selectin")


class UserTrustLevelEvent(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_trust_level_events"
    __table_args__ = (
        Index("ix_user_trust_events_user_created", "user_id", "created_at"),
        Index("ix_user_trust_events_source", "source_type", "source_id"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_level: Mapped[int] = mapped_column(Integer, nullable=False)
    next_level: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(96))
    actor_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    note: Mapped[str | None] = mapped_column(String(500))
