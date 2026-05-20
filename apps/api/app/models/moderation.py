from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.forum import Board
    from app.models.user import User

FlagTargetType = Literal["topic", "post"]
FlagReason = Literal["spam", "harassment", "off_topic", "private_info", "other"]
FlagStatus = Literal["pending", "resolved", "rejected"]
ModerationAction = Literal[
    "flag_created",
    "flag_status_changed",
    "topic_hidden",
    "topic_restored",
    "topic_status_changed",
    "topic_pinned_changed",
    "topic_moved",
    "topic_split",
    "topic_merged",
    "post_hidden",
    "post_restored",
    "post_edited",
    "post_revision_restored",
    "user_status_changed",
    "screened_rule_created",
    "screened_rule_deleted",
]
ScreenedRuleKind = Literal["email", "ip", "url"]
ScreenedRuleAction = Literal["block", "silence"]


class Flag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flags"
    __table_args__ = (
        Index("ix_flags_status_created", "status", "created_at"),
        Index("ix_flags_target", "target_type", "target_id"),
        Index("ix_flags_board_status", "board_id", "status"),
    )

    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    board: Mapped[Board] = relationship("Board", lazy="selectin")
    reporter: Mapped[User] = relationship("User", foreign_keys=[reporter_id], lazy="selectin")
    resolved_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[resolved_by_id], lazy="selectin"
    )


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_board_created", "board_id", "created_at"),
    )

    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    board_id: Mapped[str | None] = mapped_column(ForeignKey("boards.id", ondelete="SET NULL"))
    data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime]

    actor: Mapped[User | None] = relationship("User", lazy="selectin")
    board: Mapped[Board | None] = relationship("Board", lazy="selectin")


class RateLimitEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (
        Index("ix_rate_limit_events_scope_created", "scope", "identity_key", "created_at"),
        Index("ix_rate_limit_events_user_created", "user_id", "created_at"),
        Index("ix_rate_limit_events_ip_created", "ip_address", "created_at"),
    )

    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User | None] = relationship("User", lazy="selectin")


class ScreenedRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "screened_rules"
    __table_args__ = (
        UniqueConstraint("kind", "normalized_value", name="uq_screened_rules_kind_value"),
        Index("ix_screened_rules_kind", "kind"),
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="block")
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    created_by: Mapped[User | None] = relationship("User", lazy="selectin")


class SpamAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "spam_actions"
    __table_args__ = (
        Index("ix_spam_actions_user_created", "user_id", "created_at"),
        Index("ix_spam_actions_rule_created", "screened_rule_id", "created_at"),
        Index("ix_spam_actions_kind_created", "kind", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(1024))
    screened_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("screened_rules.id", ondelete="SET NULL")
    )
    data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[User | None] = relationship("User", lazy="selectin")
    screened_rule: Mapped[ScreenedRule | None] = relationship("ScreenedRule", lazy="selectin")
