"""add personal daily report assistant

Revision ID: 0069_daily_report_assistant
Revises: 0068_product_access_grants
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0069_daily_report_assistant"
down_revision: str | None = "0068_product_access_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_report_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("custom_prompt", sa.Text(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_daily_report_profiles_user"),
        comment="用户个人日报助手配置，保存当前定制 Prompt 与版本。",
    )
    op.create_table(
        "daily_report_prompt_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("custom_prompt", sa.Text(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["daily_report_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "profile_id",
            "version",
            name="uq_daily_report_prompt_versions_profile_version",
        ),
        comment="个人日报 Prompt 的只增版本快照，支持追踪和回退。",
    )
    op.create_index(
        "ix_daily_report_prompt_versions_user_created",
        "daily_report_prompt_versions",
        ["user_id", "created_at"],
    )
    op.create_table(
        "daily_report_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("current_draft", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("provider_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        comment="一次个人日报生成和多轮修改会话。",
    )
    op.create_index(
        "ix_daily_report_sessions_user_created",
        "daily_report_sessions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_daily_report_sessions_user_status",
        "daily_report_sessions",
        ["user_id", "status"],
    )
    op.create_table(
        "daily_report_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["daily_report_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_daily_report_messages_session_sequence",
        ),
        comment="日报会话内按顺序保存的用户与助手消息。",
    )
    op.create_index(
        "ix_daily_report_messages_user_created",
        "daily_report_messages",
        ["user_id", "created_at"],
    )
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_input", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["daily_report_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("session_id", name="uq_daily_reports_session"),
        comment="用户确认后的最终日报历史，用于查看、复制与表达去重。",
    )
    op.create_index(
        "ix_daily_reports_user_work_date",
        "daily_reports",
        ["user_id", "work_date"],
    )
    op.create_index(
        "ix_daily_reports_user_created",
        "daily_reports",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_reports_user_created", table_name="daily_reports")
    op.drop_index("ix_daily_reports_user_work_date", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index(
        "ix_daily_report_messages_user_created",
        table_name="daily_report_messages",
    )
    op.drop_table("daily_report_messages")
    op.drop_index(
        "ix_daily_report_sessions_user_status",
        table_name="daily_report_sessions",
    )
    op.drop_index(
        "ix_daily_report_sessions_user_created",
        table_name="daily_report_sessions",
    )
    op.drop_table("daily_report_sessions")
    op.drop_index(
        "ix_daily_report_prompt_versions_user_created",
        table_name="daily_report_prompt_versions",
    )
    op.drop_table("daily_report_prompt_versions")
    op.drop_table("daily_report_profiles")
