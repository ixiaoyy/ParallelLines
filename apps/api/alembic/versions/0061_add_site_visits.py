"""add site visit analytics

Revision ID: 0061_add_site_visits
Revises: 0060_seed_xiaoxiao_chick_user
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0061_add_site_visits"
down_revision: str | None = "0060_seed_xiaoxiao_chick_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the immutable site visit event table.

    Key parameters: none. Return value: none. Side effect: creates
    `site_visits` and indexes used by PV/UV, source, and entry-page reports.
    """

    op.create_table(
        "site_visits",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "visitor_key",
            sa.String(length=96),
            nullable=False,
            comment="访问者去重键；保存登录用户或匿名访客标识的哈希，不保存原始访客 ID。",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=True,
            comment="登录访问者用户 ID；匿名访问为空。",
        ),
        sa.Column(
            "path",
            sa.String(length=512),
            nullable=False,
            comment="访问的站内路径，包含查询字符串但不包含域名。",
        ),
        sa.Column(
            "title",
            sa.String(length=180),
            nullable=True,
            comment="访问时浏览器页面标题；为空表示前端未提供。",
        ),
        sa.Column(
            "referrer_host",
            sa.String(length=255),
            nullable=True,
            comment="来源 URL 的主机名；直接访问或无法解析时为空。",
        ),
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            comment="访问来源类型：direct、internal、search、social、referral 或 campaign。",
        ),
        sa.Column(
            "source_name",
            sa.String(length=255),
            nullable=False,
            comment="归一化来源名称，如 Direct、Internal、baidu.com 或 utm_source。",
        ),
        sa.Column(
            "utm_source",
            sa.String(length=128),
            nullable=True,
            comment="URL 查询参数 utm_source；为空表示未带广告/活动来源。",
        ),
        sa.Column(
            "utm_medium",
            sa.String(length=128),
            nullable=True,
            comment="URL 查询参数 utm_medium；为空表示未带媒介。",
        ),
        sa.Column(
            "utm_campaign",
            sa.String(length=180),
            nullable=True,
            comment="URL 查询参数 utm_campaign；为空表示未带活动名称。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="访问事件记录时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="站点访问事件，用于统计 PV、UV、来源渠道和入口页。",
    )
    op.create_index("ix_site_visits_created", "site_visits", ["created_at"])
    op.create_index(
        "ix_site_visits_visitor_created",
        "site_visits",
        ["visitor_key", "created_at"],
    )
    op.create_index(
        "ix_site_visits_source_created",
        "site_visits",
        ["source_type", "source_name", "created_at"],
    )
    op.create_index("ix_site_visits_path_created", "site_visits", ["path", "created_at"])
    op.create_index("ix_site_visits_user_created", "site_visits", ["user_id", "created_at"])


def downgrade() -> None:
    """Drop site visit analytics storage on schema downgrade.

    Key parameters: none. Return value: none. Side effect: removes the
    `site_visits` table and its indexes.
    """

    op.drop_index("ix_site_visits_user_created", table_name="site_visits")
    op.drop_index("ix_site_visits_path_created", table_name="site_visits")
    op.drop_index("ix_site_visits_source_created", table_name="site_visits")
    op.drop_index("ix_site_visits_visitor_created", table_name="site_visits")
    op.drop_index("ix_site_visits_created", table_name="site_visits")
    op.drop_table("site_visits")
