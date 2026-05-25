"""add subscriptions and payment events

Revision ID: 0029_subscriptions_payments
Revises: 0028_chat_presence
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_subscriptions_payments"
down_revision: str | None = "0028_chat_presence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="会员计划 ID。"),
        sa.Column("slug", sa.String(length=80), nullable=False, comment="计划稳定标识。"),
        sa.Column("name", sa.String(length=120), nullable=False, comment="计划显示名称。"),
        sa.Column("description", sa.Text(), nullable=True, comment="计划说明。"),
        sa.Column("price_cents", sa.Integer(), nullable=False, comment="价格，单位为分。"),
        sa.Column(
            "currency", sa.String(length=8), nullable=False, server_default="CNY", comment="币种。"
        ),
        sa.Column(
            "interval",
            sa.String(length=16),
            nullable=False,
            server_default="month",
            comment="计费周期：month 或 year。",
        ),
        sa.Column("entitlements", sa.JSON(), nullable=False, comment="权益 key 列表。"),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否可购买。"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.UniqueConstraint("slug", name="uq_subscription_plans_slug"),
        comment="付费会员计划及其权益定义。",
    )

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="订阅记录 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="订阅用户 ID。"),
        sa.Column("plan_id", sa.BigInteger(), nullable=False, comment="计划 ID。"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
            comment="订阅状态。",
        ),
        sa.Column("provider", sa.String(length=32), nullable=False, comment="支付 provider。"),
        sa.Column(
            "provider_customer_id",
            sa.String(length=120),
            nullable=True,
            comment="provider 客户 ID。",
        ),
        sa.Column(
            "provider_subscription_id",
            sa.String(length=160),
            nullable=False,
            comment="provider 订阅 ID。",
        ),
        sa.Column(
            "current_period_start",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="当前周期开始时间。",
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="当前周期结束时间。",
        ),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否周期结束后取消。",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        comment="用户订阅状态和当前周期。",
    )
    op.create_index(
        "ix_user_subscriptions_user_status", "user_subscriptions", ["user_id", "status"]
    )
    op.create_index(
        "ix_user_subscriptions_provider",
        "user_subscriptions",
        ["provider", "provider_subscription_id"],
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="支付事件 ID。"),
        sa.Column("provider", sa.String(length=32), nullable=False, comment="支付 provider。"),
        sa.Column("event_id", sa.String(length=160), nullable=False, comment="provider 事件 ID。"),
        sa.Column("event_type", sa.String(length=120), nullable=False, comment="事件类型。"),
        sa.Column("user_id", sa.BigInteger(), nullable=True, comment="关联用户 ID。"),
        sa.Column("plan_id", sa.BigInteger(), nullable=True, comment="关联计划 ID。"),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True, comment="关联订阅 ID。"),
        sa.Column("amount_cents", sa.Integer(), nullable=True, comment="金额，单位分。"),
        sa.Column("currency", sa.String(length=8), nullable=True, comment="币种。"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="处理状态。"),
        sa.Column(
            "signature_valid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="签名是否有效。",
        ),
        sa.Column("payload", sa.JSON(), nullable=False, comment="脱敏后的 webhook payload。"),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=True, comment="处理完成时间。"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["user_subscriptions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_events_provider_event"),
        comment="支付 provider webhook 事件处理记录。",
    )
    op.create_index("ix_payment_events_user_created", "payment_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_user_created", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("ix_user_subscriptions_provider", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_status", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
    op.drop_table("subscription_plans")
