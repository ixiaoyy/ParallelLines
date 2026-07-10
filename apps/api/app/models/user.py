from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import USER_ROLE_USER
from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type

UserRole = Literal["user", "moderator", "admin"]
UserStatus = Literal["pending_verification", "active", "silenced", "suspended", "deleted"]


class User(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_is_persona_created_at", "is_persona", "created_at"),
    )

    username: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    display_name: Mapped[str | None] = mapped_column(
        String(80),
        comment="公开昵称；为空时使用 username。",
    )
    bio: Mapped[str | None] = mapped_column(Text, comment="个人简介；按资料隐私设置公开。")
    website_url: Mapped[str | None] = mapped_column(
        String(512),
        comment="个人链接 URL；按资料隐私设置公开。",
    )
    location: Mapped[str | None] = mapped_column(
        String(120),
        comment="个人所在地或时区文本；按资料隐私设置公开。",
    )
    role: Mapped[str] = mapped_column(String(32), default=USER_ROLE_USER, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trust_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trust_level_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    experience_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_persona: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为运营维护的马甲账号；真实用户增长统计必须排除。",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_factor_secret: Mapped[str | None] = mapped_column(String(64))
    profile_visibility: Mapped[str] = mapped_column(
        String(16),
        default="public",
        nullable=False,
        comment="资料可见性：public、members 或 private。",
    )
    show_activity: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否在公开资料页展示活动流。",
    )
    interface_theme: Mapped[str] = mapped_column(
        String(32),
        default="system",
        nullable=False,
        comment="个人界面偏好：system、light 或 colorful。",
    )
    locale: Mapped[str] = mapped_column(
        String(16),
        default="zh-CN",
        nullable=False,
        comment="个人界面语言偏好。",
    )

    @property
    def experience_to_next_level(self) -> int:
        from app.core.growth import experience_to_next_level

        return experience_to_next_level(self.experience_total)

    @property
    def level_progress_percent(self) -> int:
        from app.core.growth import level_progress_percent

        return level_progress_percent(self.experience_total)

    @property
    def trust_level_label(self) -> str:
        from app.core.trust import trust_level_label

        return trust_level_label(self.trust_level)


class UserPointEvent(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_point_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_user_point_events_idempotency_key"),
        Index("ix_user_point_events_user_created", "user_id", "created_at"),
        Index("ix_user_point_events_source_created", "source_type", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(96))
    points_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    experience_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    experience_after: Mapped[int] = mapped_column(Integer, nullable=False)
    level_after: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))


class EmailVerificationCode(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_verification_codes"
    __table_args__ = (Index("ix_email_verification_codes_user_sent", "user_id", "sent_at"),)

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserSecurityToken(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_security_tokens"
    __table_args__ = (
        Index("ix_user_security_tokens_user_purpose", "user_id", "purpose"),
        UniqueConstraint("token_hash", name="uq_user_security_tokens_token_hash"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserSession(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_revoked", "user_id", "revoked_at"),)

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserRecoveryCode(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_recovery_codes"
    __table_args__ = (Index("ix_user_recovery_codes_user_used", "user_id", "used_at"),)

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
