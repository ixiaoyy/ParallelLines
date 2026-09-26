"""Add Fengling Town while preserving existing catalog entries and statistics.

Revision ID: 0082_add_fengling_town
Revises: 0081_catalog_games_and_views
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0082_add_fengling_town"
down_revision: str | None = "0081_catalog_games_and_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """将风铃小城追加到闯关分类；相同标识或根网址已收录时保留原记录。"""

    bind = op.get_bind()
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = 'stages'")
    )
    # 所需分类缺失时直接终止，不创建额外分类或写入不完整项目。
    if category_id is None:
        raise RuntimeError("0082 requires catalog category stages")

    slug = "fengling-town"
    url = "https://uffv.de/"
    # 根网址的末尾斜线不区分新项目；已有记录的人工编辑和统计全部保留。
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
    # 追加到现有分类末尾，浏览次数沿用 0081 的数据库默认值零。
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
            "name": "风铃小城",
            "url": url,
            "description": "在山城中二段跳、攀墙和滑翔，沿不同路线登上千米钟塔。",
            "author_name": "hui455",
            "author_url": "https://linux.do/u/hui455/summary",
            "sort_order": next_order,
            "now": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    """只回退版本号，保留游戏、人工编辑及新增后的浏览和评分记录。"""

    # 游戏已有后续使用数据时不能自动删除，需要撤下可由管理员隐藏。
    pass
