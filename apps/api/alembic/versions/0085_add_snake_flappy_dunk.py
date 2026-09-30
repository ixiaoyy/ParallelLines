"""Add two internal games without changing the catalog schema.

Revision ID: 0085_add_snake_flappy_dunk
Revises: 0084_add_backrooms
Create Date: 2026-09-30
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0085_add_snake_flappy_dunk"
down_revision: str | None = "0084_add_backrooms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加两个站内游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    projects = (
        (
            "puzzle",
            "snake-escape",
            "蛇蛇出洞",
            "/play/snake-escape",
            "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
        ),
        (
            "casual",
            "flappy-dunk",
            "飞翼灌篮",
            "/play/flappy-dunk",
            "点按让带翅膀的篮球跳跃，从上方穿过篮圈，挑战连续进球和最高分。",
        ),
    )
    # 先核对两个现有分类，缺失时在任何插入前终止，避免只收录一半。
    categories = dict(
        bind.execute(
            sa.text("SELECT slug, id FROM catalog_categories WHERE slug IN ('puzzle', 'casual')")
        ).all()
    )
    if any(slug not in categories for slug in ("puzzle", "casual")):
        raise RuntimeError("0085 requires catalog categories puzzle and casual")

    now = datetime.now(UTC)
    for category_slug, slug, name, url, description in projects:
        # 地址末尾斜线视为同一游戏；不改写已存在的管理员记录。
        existing_id = bind.scalar(
            sa.text(
                "SELECT id FROM catalog_projects WHERE slug = :slug "
                "OR destination_url IN (:url, :url_with_slash) LIMIT 1"
            ),
            {"slug": slug, "url": url, "url_with_slash": f"{url}/"},
        )
        if existing_id is not None:
            continue

        category_id = categories[category_slug]
        # 隐藏条目也参与追加排序；浏览次数沿用数据库默认值零。
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
        bind.execute(
            sa.text(
                "INSERT INTO catalog_projects "
                "(category_id, slug, name, destination_url, destination_kind, description, "
                "author_name, author_url, sort_order, is_visible, created_at, updated_at) "
                "VALUES (:category_id, :slug, :name, :url, 'internal', :description, "
                "NULL, NULL, :sort_order, TRUE, :now, :now)"
            ),
            {
                "category_id": category_id,
                "slug": slug,
                "name": name,
                "url": url,
                "description": description,
                "sort_order": next_order,
                "now": now,
            },
        )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的使用数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
