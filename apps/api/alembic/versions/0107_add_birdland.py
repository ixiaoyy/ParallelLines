"""收录 BIRDLAND 英文原版独立入口，保留已有目录内容与统计。

Revision ID: 0107_add_birdland
Revises: 0106_add_direct_game_sites
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0107_add_birdland"
down_revision: str | None = "0106_add_direct_game_sites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加英文原版；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 使用已有恋爱分类；缺失时在首写前终止，不创建或调整分类。
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
        {"slug": "romance"},
    )
    if category_id is None:
        raise RuntimeError("0107 requires catalog category romance")

    slug = "birdland"
    url = "https://birdland.camp/"
    # 包含隐藏和跨分类记录；外链仅有末尾斜线差异时视为同一作品。
    url_without_slash = url.rstrip("/")
    existing_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE slug = :slug "
            "OR destination_url IN (:url_without_slash, :url_with_slash) LIMIT 1"
        ),
        {
            "slug": slug,
            "url_without_slash": url_without_slash,
            "url_with_slash": f"{url_without_slash}/",
        },
    )
    if existing_id is not None:
        return

    # 隐藏条目也参与分类末尾排序；新项目浏览次数沿用默认值零。
    next_order = (
        int(
            bind.scalar(
                sa.text(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
        )
        + 1
    )
    now = datetime.now(UTC)
    # 游戏入口直达英文原版，作者链接另指公开列出写作与美术署名的作品页。
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
            "name": "BIRDLAND",
            "url": url,
            "description": (
                "英文文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
                "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
            ),
            "author_name": "Brendan Patrick Hennessy / Izzy Marbella",
            "author_url": "https://bphennessy.itch.io/birdland",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
