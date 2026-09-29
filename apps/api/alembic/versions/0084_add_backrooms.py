"""Add Backrooms while preserving existing catalog entries and statistics.

Revision ID: 0084_add_backrooms
Revises: 0083_add_double_feature
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0084_add_backrooms"
down_revision: str | None = "0083_add_double_feature"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """将后室追加到恐怖分类；相同标识或根网址已收录时保留原记录。"""

    bind = op.get_bind()
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = 'horror'")
    )
    # 所需分类缺失时直接终止，不创建额外分类或写入不完整项目。
    if category_id is None:
        raise RuntimeError("0084 requires catalog category horror")

    slug = "backrooms"
    url = "https://ho.wangzhuge.cc.cd/"
    # 根网址的末尾斜线不区分新项目；已有记录的人工编辑、隐藏状态和统计全部保留。
    existing_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE slug = :slug "
            "OR destination_url IN (:url, :url_without_slash) LIMIT 1"
        ),
        {"slug": slug, "url": url, "url_without_slash": url.rstrip("/")},
    )
    if existing_id is not None:
        return

    next_order = int(
        bind.scalar(
            sa.text(
                "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                "WHERE category_id = :category_id"
            ),
            {"category_id": category_id},
        )
    ) + 1
    # 包含隐藏项目计算分类末尾，浏览次数沿用数据库默认值零。
    bind.execute(
        sa.text(
            "INSERT INTO catalog_projects "
            "(category_id, slug, name, destination_url, destination_kind, description, "
            "author_name, author_url, sort_order, is_visible, created_at, updated_at) "
            "VALUES (:category_id, :slug, :name, :url, 'external', :description, "
            ":author_name, :author_url, :sort_order, TRUE, :now, :now)"
        ),
        {
            "category_id": category_id,
            "slug": slug,
            "name": "后室",
            "url": url,
            "description": (
                "第一人称后室恐怖探索游戏，穿行不同层级、寻找线索与补给，"
                "在实体追逐中求生。"
            ),
            "author_name": "wangzhuge",
            "author_url": "https://linux.do/u/wangzhuge",
            "sort_order": next_order,
            "now": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    """只回退版本号，保留游戏、人工编辑及新增后的浏览和评分记录。"""

    # 游戏已有后续使用数据时不能自动删除，需要撤下可由管理员隐藏。
    pass
