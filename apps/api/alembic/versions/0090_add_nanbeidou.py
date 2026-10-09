"""收录 NANBEIDOU，保留已有目录内容与统计。

Revision ID: 0090_add_nanbeidou
Revises: 0089_add_three_external_games
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0090_add_nanbeidou"
down_revision: str | None = "0089_add_three_external_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加 NANBEIDOU；已有标识或地址的内容、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 复用现有卡牌分类；分类缺失时在插入前终止，不另建分类或更改归属。
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": "cards"}
    )
    if category_id is None:
        raise RuntimeError("0090 requires catalog category cards")

    slug = "nanbeidou"
    url = "https://opea.de5.net/rpg"
    # 外部地址有无末尾斜线均视为同一游戏；包括隐藏和其他分类的已有记录。
    existing_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE slug = :slug "
            "OR destination_url IN (:url, :url_with_slash) LIMIT 1"
        ),
        {"slug": slug, "url": url, "url_with_slash": f"{url}/"},
    )
    if existing_id is not None:
        return

    # 隐藏项目也参与分类末尾排序；空分类从零开始，新项目浏览次数沿用默认值零。
    next_order = int(
        bind.scalar(
            sa.text(
                "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                "WHERE category_id = :category_id"
            ),
            {"category_id": category_id},
        )
    ) + 1
    now = datetime.now(UTC)
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
            "name": "NANBEIDOU",
            "url": url,
            "description": (
                "像素风回合制卡牌冒险，组建队伍探索异世界，在剧情中解锁角色；"
                "也可选择混战或地主模式，结合手牌、装备和角色技能对战。"
            ),
            "author_name": "sehsapneb",
            "author_url": "https://linux.do/u/sehsapneb/summary",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
