"""add calendar events and rsvps

Revision ID: 0030_calendar_events
Revises: 0029_subscriptions_payments
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_calendar_events"
down_revision: str | None = "0029_subscriptions_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="活动 ID。"),
        sa.Column("title", sa.String(length=180), nullable=False, comment="活动标题。"),
        sa.Column("description", sa.Text(), nullable=True, comment="活动说明。"),
        sa.Column("topic_id", sa.BigInteger(), nullable=True, comment="关联活动主题 ID。"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False, comment="创建者 ID。"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, comment="开始时间 UTC。"),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False, comment="结束时间 UTC。"),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
            comment="活动时区。",
        ),
        sa.Column("location", sa.String(length=200), nullable=True, comment="地点或线上链接。"),
        sa.Column("capacity", sa.Integer(), nullable=True, comment="报名上限；为空表示不限。"),
        sa.Column(
            "rsvp_deadline", sa.DateTime(timezone=True), nullable=True, comment="报名截止时间。"
        ),
        sa.Column(
            "reminder_minutes_before",
            sa.Integer(),
            nullable=False,
            server_default="60",
            comment="提醒提前分钟数。",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        comment="社区日历活动，支持 RSVP、时区和 iCal 订阅。",
    )
    op.create_index("ix_calendar_events_start_end", "calendar_events", ["start_at", "end_at"])
    op.create_index(
        "ix_calendar_events_creator", "calendar_events", ["created_by_id", "created_at"]
    )

    op.create_table(
        "event_rsvps",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="活动报名 ID。"),
        sa.Column("event_id", sa.BigInteger(), nullable=False, comment="活动 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="报名用户 ID。"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="going",
            comment="状态：going 或 canceled。",
        ),
        sa.Column(
            "reminder_sent_at", sa.DateTime(timezone=True), nullable=True, comment="提醒发送时间。"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["event_id"], ["calendar_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_rsvps_event_user"),
        comment="活动 RSVP/报名记录和提醒发送状态。",
    )
    op.create_index("ix_event_rsvps_user_status", "event_rsvps", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_event_rsvps_user_status", table_name="event_rsvps")
    op.drop_table("event_rsvps")
    op.drop_index("ix_calendar_events_creator", table_name="calendar_events")
    op.drop_index("ix_calendar_events_start_end", table_name="calendar_events")
    op.drop_table("calendar_events")
