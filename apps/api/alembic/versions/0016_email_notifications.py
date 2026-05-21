"""add email notification preferences and webhooks

Revision ID: 0016_email_notifications
Revises: 0015_background_jobs
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_email_notifications"
down_revision: str | None = "0015_background_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_email_preferences",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "user_id", sa.String(length=36), nullable=False, comment="偏好所属用户 ID，唯一。"
        ),
        sa.Column(
            "email_enabled", sa.Boolean(), nullable=False, comment="是否允许向该用户发送社区邮件。"
        ),
        sa.Column("notify_replied", sa.Boolean(), nullable=False, comment="被回复时是否发送邮件。"),
        sa.Column(
            "notify_mentioned", sa.Boolean(), nullable=False, comment="被提及时是否发送邮件。"
        ),
        sa.Column(
            "notify_liked", sa.Boolean(), nullable=False, comment="帖子被点赞时是否发送邮件。"
        ),
        sa.Column(
            "notify_topic_new_post",
            sa.Boolean(),
            nullable=False,
            comment="关注主题有新回复时是否发送邮件。",
        ),
        sa.Column(
            "notify_board_new_topic",
            sa.Boolean(),
            nullable=False,
            comment="关注版块有新主题时是否发送邮件。",
        ),
        sa.Column(
            "digest_frequency",
            sa.String(length=16),
            nullable=False,
            comment="摘要邮件频率：off、daily 或 weekly。",
        ),
        sa.Column(
            "last_digest_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="上次摘要邮件发送时间；为空表示从未发送。",
        ),
        sa.Column(
            "delivery_status",
            sa.String(length=32),
            nullable=False,
            comment="邮件投递状态：ok、bounced、complained 或 disabled。",
        ),
        sa.Column(
            "disabled_reason",
            sa.String(length=255),
            nullable=True,
            comment="邮件被自动或手动停发的原因；为空表示未停发。",
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_email_preferences_user"),
        comment="用户邮件通知、摘要频率和投递禁用状态。",
    )
    op.create_index(
        "ix_user_email_preferences_digest",
        "user_email_preferences",
        ["digest_frequency", "last_digest_sent_at"],
        unique=False,
    )
    op.create_table(
        "email_delivery_events",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=True,
            comment="匹配到的用户 ID；未知邮箱为空。",
        ),
        sa.Column(
            "email", sa.String(length=255), nullable=False, comment="投递事件涉及的邮箱地址。"
        ),
        sa.Column(
            "event_type",
            sa.String(length=32),
            nullable=False,
            comment="事件类型：sent、delivered、bounce、complaint 或 dropped。",
        ),
        sa.Column("kind", sa.String(length=64), nullable=True, comment="邮件业务类型。"),
        sa.Column(
            "provider_message_id",
            sa.String(length=255),
            nullable=True,
            comment="邮件供应商消息 ID；为空表示供应商未提供。",
        ),
        sa.Column("reason", sa.Text(), nullable=True, comment="退信、投诉或丢弃原因摘要。"),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
            comment="供应商原始事件的安全摘录，不包含认证密钥。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="事件记录时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="邮件供应商投递、退信和投诉事件记录。",
    )
    op.create_index("ix_email_delivery_events_email", "email_delivery_events", ["email"])
    op.create_index(
        "ix_email_delivery_events_email_created",
        "email_delivery_events",
        ["email", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_delivery_events_user_created",
        "email_delivery_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "from_email", sa.String(length=255), nullable=False, comment="入站邮件发件人邮箱。"
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=True,
            comment="匹配到的站内用户 ID；未知发件人为空。",
        ),
        sa.Column(
            "topic_id", sa.String(length=36), nullable=True, comment="邮件声称回复的主题 ID。"
        ),
        sa.Column(
            "post_id", sa.String(length=36), nullable=True, comment="邮件声称回复的父帖子 ID。"
        ),
        sa.Column(
            "provider_message_id",
            sa.String(length=255),
            nullable=True,
            comment="入站邮件供应商消息 ID。",
        ),
        sa.Column(
            "raw_md", sa.Text(), nullable=False, comment="入站邮件转换后的 Markdown/纯文本正文。"
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="处理状态：accepted、unknown_sender、topic_not_found 或 recorded。",
        ),
        sa.Column("reason", sa.Text(), nullable=True, comment="未接受或仅记录的原因摘要。"),
        sa.Column(
            "payload", sa.JSON(), nullable=False, comment="入站 webhook 原始上下文的安全摘录。"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入站邮件记录时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="入站邮件回复 webhook 记录及匹配状态。",
    )
    op.create_index("ix_inbound_emails_from_email", "inbound_emails", ["from_email"])
    op.create_index(
        "ix_inbound_emails_status_created",
        "inbound_emails",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inbound_emails_topic_created",
        "inbound_emails",
        ["topic_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_emails_topic_created", table_name="inbound_emails")
    op.drop_index("ix_inbound_emails_status_created", table_name="inbound_emails")
    op.drop_index("ix_inbound_emails_from_email", table_name="inbound_emails")
    op.drop_table("inbound_emails")
    op.drop_index("ix_email_delivery_events_user_created", table_name="email_delivery_events")
    op.drop_index("ix_email_delivery_events_email_created", table_name="email_delivery_events")
    op.drop_index("ix_email_delivery_events_email", table_name="email_delivery_events")
    op.drop_table("email_delivery_events")
    op.drop_index("ix_user_email_preferences_digest", table_name="user_email_preferences")
    op.drop_table("user_email_preferences")
