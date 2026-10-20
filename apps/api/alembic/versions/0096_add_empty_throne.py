"""收录空王座，保留已有目录内容与统计。

Revision ID: 0096_add_empty_throne
Revises: 0095_add_reverse_snake_3d
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0096_add_empty_throne"
down_revision: str | None = "0095_add_reverse_snake_3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加空王座；已有标识或地址的内容、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 复用现有角色扮演分类；分类缺失时在插入前终止，不另建分类或更改归属。
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": "rpg"}
    )
    if category_id is None:
        raise RuntimeError("0096 requires catalog category rpg")

    slug = "empty-throne"
    url = "https://muselabs.co/empty-throne"
    # 外部地址有无末尾斜线均视为同一游戏；包括隐藏和其他分类的已有记录。
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
            "name": "空王座 · 白鹭王国的冒险",
            "url": url,
            "description": (
                "选择战士、法师或牧师，探索白鹭王国的六章故事，"
                "通过战斗、调查与推理揭开王座背后的阴谋，支持中英日三语配音。"
            ),
            "author_name": "_westfall",
            "author_url": "https://linux.do/u/_westfall/summary",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
