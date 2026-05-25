"""add push subscriptions

Revision ID: 0033_push_subscriptions
Revises: 0032_ai_topic_summaries
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_push_subscriptions"
down_revision: str | None = "0032_ai_topic_summaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间（UTC）。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录最后更新时间（UTC）。",
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="订阅所属用户 ID。"),
        sa.Column(
            "endpoint",
            sa.String(length=512),
            nullable=False,
            comment="浏览器 PushSubscription endpoint，用于去重；响应会安全截断展示。",
        ),
        sa.Column(
            "p256dh", sa.String(length=255), nullable=False, comment="Web Push p256dh 公钥。"
        ),
        sa.Column(
            "auth_secret", sa.String(length=255), nullable=False, comment="Web Push auth 密钥。"
        ),
        sa.Column(
            "user_agent",
            sa.String(length=500),
            nullable=True,
            comment="订阅设备浏览器 User-Agent 摘要。",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="该推送订阅是否仍启用。",
        ),
        sa.Column(
            "last_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最近一次尝试推送通知时间；为空表示尚未发送。",
        ),
        sa.Column(
            "disabled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="用户撤销或浏览器失效时间；为空表示仍启用。",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        comment="用户 Web Push 订阅端点，保存浏览器加密密钥、启用状态和撤销时间。",
    )
    op.create_index(
        "ix_push_subscriptions_user_enabled",
        "push_subscriptions",
        ["user_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_enabled", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
