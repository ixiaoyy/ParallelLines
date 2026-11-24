"""新增隔离的跨站事件、访客与日汇总表；不改动或回填既有业务数据。

Revision ID: 0113_cross_site_traffic
Revises: 0112_space_capsule_status
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0113_cross_site_traffic"
down_revision: str | None = "0112_space_capsule_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "traffic_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("site_key", sa.String(16), nullable=False),
        sa.Column("visitor_key", sa.String(96), nullable=False),
        sa.Column("identity_scope", sa.String(16), nullable=False),
        sa.Column("event_name", sa.String(24), nullable=False),
        sa.Column("path", sa.String(256), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    for suffix, columns in (
        ("site_occurred", ["site_key", "occurred_at"]),
        ("visitor_occurred", ["visitor_key", "occurred_at"]),
        ("occurred", ["occurred_at"]),
        ("received", ["received_at"]),
        ("site_received", ["site_key", "received_at"]),
    ):
        op.create_index(f"ix_traffic_events_{suffix}", "traffic_events", columns)
    op.create_table(
        "traffic_visitors",
        sa.Column("site_key", sa.String(16), primary_key=True),
        sa.Column("visitor_key", sa.String(96), primary_key=True),
        sa.Column("identity_scope", sa.String(16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_traffic_visitors_first_seen", "traffic_visitors", ["site_key", "first_seen_at"]
    )
    op.create_table(
        "traffic_daily_visitors",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("site_key", sa.String(16), primary_key=True),
        sa.Column("visitor_key", sa.String(96), primary_key=True),
        sa.Column("identity_scope", sa.String(16), nullable=False),
        sa.Column("page_views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("actions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shared_page_views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_traffic_daily_site_day", "traffic_daily_visitors", ["site_key", "day"])
    op.create_index(
        "ix_traffic_daily_visitor_day", "traffic_daily_visitors", ["site_key", "visitor_key", "day"]
    )


def downgrade() -> None:
    # 仅人工确认恢复时执行；会删除本功能统计，旧站点访问和业务表不受影响。
    op.drop_table("traffic_daily_visitors")
    op.drop_table("traffic_visitors")
    op.drop_table("traffic_events")
