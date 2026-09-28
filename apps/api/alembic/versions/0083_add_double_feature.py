"""Add Double Feature while preserving existing catalog entries and statistics.

Revision ID: 0083_add_double_feature
Revises: 0082_add_fengling_town
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0083_add_double_feature"
down_revision: str | None = "0082_add_fengling_town"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """将 Double Feature 追加到射击分类；标识或完整网址已收录时保留原记录。"""

    bind = op.get_bind()
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = 'shooting'")
    )
    # 所需分类缺失时直接终止，不创建额外分类或写入不完整项目。
    if category_id is None:
        raise RuntimeError("0083 requires catalog category shooting")

    slug = "double-feature"
    url = "https://claude.ai/artifact/Vos8wdB8Jenz9FopZWeRMb"
    # 按标识或完整作品网址去重，保留已有记录的人工编辑、隐藏状态和统计。
    existing_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE slug = :slug "
            "OR destination_url = :url LIMIT 1"
        ),
        {"slug": slug, "url": url},
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
    # 包含隐藏项目计算分类末尾；不设置封面，浏览次数沿用数据库默认值零。
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
            "name": "Double Feature",
            "url": url,
            "description": (
                "受《茶杯头》启发的复古卡通射击小游戏。"
                "作者称使用 Claude Opus 5.5 制作画面与音效。"
            ),
            "author_name": "Sestina",
            "author_url": "https://x.com/TaylorBereiter",
            "sort_order": next_order,
            "now": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    """只回退版本号，保留游戏、人工编辑及新增后的浏览和评分记录。"""

    # 游戏已有后续使用数据时不能自动删除，需要撤下可由管理员隐藏。
    pass
