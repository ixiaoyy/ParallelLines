from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

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

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

SubscriptionInterval = Literal["month", "year"]
SubscriptionStatus = Literal["active", "past_due", "canceled", "expired"]


class SubscriptionPlan(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_subscription_plans_slug"),
        {"comment": "付费会员计划及其权益定义。"},
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False, comment="计划稳定标识。")
    name: Mapped[str] = mapped_column(String(120), nullable=False, comment="计划显示名称。")
    description: Mapped[str | None] = mapped_column(Text, comment="计划说明；为空表示无说明。")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, comment="价格，单位为分。")
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="CNY", comment="币种。"
    )
    interval: Mapped[str] = mapped_column(
        String(16), nullable=False, default="month", comment="计费周期：month 或 year。"
    )
    entitlements: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, comment="该计划授予的权益 key 列表。"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否可购买。"
    )


class UserSubscription(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        Index("ix_user_subscriptions_user_status", "user_id", "status"),
        Index("ix_user_subscriptions_provider", "provider", "provider_subscription_id"),
        {"comment": "用户订阅状态和当前周期。"},
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="订阅用户 ID。"
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        comment="计划 ID。",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", comment="订阅状态。"
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付 provider。")
    provider_customer_id: Mapped[str | None] = mapped_column(
        String(120), comment="provider 客户 ID；为空表示尚未同步。"
    )
    provider_subscription_id: Mapped[str] = mapped_column(
        String(160), nullable=False, comment="provider 订阅 ID。"
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="当前订阅周期开始时间。"
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="当前订阅周期结束时间。"
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否周期结束后取消。"
    )

    user: Mapped[User] = relationship("User", lazy="selectin")
    plan: Mapped[SubscriptionPlan] = relationship("SubscriptionPlan", lazy="selectin")


class PaymentEvent(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_payment_events_provider_event"),
        Index("ix_payment_events_user_created", "user_id", "created_at"),
        {"comment": "支付 provider webhook 事件处理记录。"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付 provider。")
    event_id: Mapped[str] = mapped_column(String(160), nullable=False, comment="provider 事件 ID。")
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, comment="事件类型。")
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), comment="关联用户 ID；无法解析时为空。"
    )
    plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="SET NULL"), comment="关联计划 ID。"
    )
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_subscriptions.id", ondelete="SET NULL"), comment="关联订阅记录 ID。"
    )
    amount_cents: Mapped[int | None] = mapped_column(Integer, comment="事件金额，单位分。")
    currency: Mapped[str | None] = mapped_column(String(8), comment="事件币种。")
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="事件处理状态。")
    signature_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Webhook 签名是否有效。"
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, comment="脱敏后的 webhook 原始 payload。"
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="事件处理完成时间；为空表示未完成。"
    )
