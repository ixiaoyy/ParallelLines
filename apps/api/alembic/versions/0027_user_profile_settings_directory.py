"""add user profile settings directory

Revision ID: 0027_user_profile_settings
Revises: 0026_api_keys_webhooks
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_user_profile_settings"
down_revision: str | None = "0026_api_keys_webhooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "display_name",
            sa.String(length=80),
            nullable=True,
            comment="公开昵称；为空时使用 username。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "bio",
            sa.Text(),
            nullable=True,
            comment="个人简介；按资料隐私设置公开。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "website_url",
            sa.String(length=512),
            nullable=True,
            comment="个人链接 URL；按资料隐私设置公开。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "location",
            sa.String(length=120),
            nullable=True,
            comment="个人所在地或时区文本；按资料隐私设置公开。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "profile_visibility",
            sa.String(length=16),
            nullable=False,
            server_default="public",
            comment="资料可见性：public、members 或 private。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "show_activity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="是否在公开资料页展示活动流。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "interface_theme",
            sa.String(length=32),
            nullable=False,
            server_default="system",
            comment="个人界面偏好：system、light 或 colorful。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(length=16),
            nullable=False,
            server_default="zh-CN",
            comment="个人界面语言偏好。",
        ),
    )
    op.create_index(
        "ix_users_profile_directory",
        "users",
        ["status", "profile_visibility", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_profile_directory", table_name="users")
    op.drop_column("users", "locale")
    op.drop_column("users", "interface_theme")
    op.drop_column("users", "show_activity")
    op.drop_column("users", "profile_visibility")
    op.drop_column("users", "location")
    op.drop_column("users", "website_url")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
