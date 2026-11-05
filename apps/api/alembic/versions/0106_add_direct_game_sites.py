"""收录三款独立游戏入口，保留已有目录内容与统计。

Revision ID: 0106_add_direct_game_sites
Revises: 0105_catalog_direct_entries
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0106_add_direct_game_sites"
down_revision: str | None = "0105_catalog_direct_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加三款直达游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 同开发者共用已核实的官方作者地址；网页试玩明确区别于另售完整版。
    projects = (
        (
            "tower-defense",
            "yorg-io",
            "YORG.io",
            "https://yorg.io/",
            "建立采矿与资源运输网络，为防御塔生产并输送弹药，抵御僵尸并保护基地。",
            "Tobias Springer / tobspr Games",
            "https://tobspr.io/",
        ),
        (
            "simulation",
            "shapez-demo",
            "shapez（网页试玩版）",
            "https://shapez.io/",
            "通过切割、旋转、合并和涂色加工形状，搭建自动化工厂；"
            "本入口为网页试玩版，完整版另售。",
            "Tobias Springer / tobspr Games",
            "https://tobspr.io/",
        ),
        (
            "shooting",
            "ztype",
            "ZType",
            "https://zty.pe/",
            "通过键入屏幕上的英文单词击毁目标的打字射击游戏，使用键盘操作。",
            "Dominic Szablewski / PhobosLab",
            "https://phoboslab.org/",
        ),
    )
    # 先核齐本批全部分类；缺少任一分类时在插入前终止，避免部分收录。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('tower-defense', 'simulation', 'shooting')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("tower-defense", "simulation", "shooting")):
        raise RuntimeError(
            "0106 requires catalog categories tower-defense, simulation and shooting"
        )

    now = datetime.now(UTC)
    for category_slug, slug, name, url, description, author_name, author_url in projects:
        # 隐藏、跨分类记录同样防重；外链仅有末尾斜线差异时视为同一作品。
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
            continue

        category_id = categories[category_slug]
        # 隐藏条目也参与末尾排序；新项目浏览次数沿用默认值零。
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
                "VALUES (:category_id, :slug, :name, :url, 'external', :description, "
                ":author_name, :author_url, :sort_order, TRUE, :now, :now)"
            ),
            {
                "category_id": category_id,
                "slug": slug,
                "name": name,
                "url": url,
                "description": description,
                "author_name": author_name,
                "author_url": author_url,
                "sort_order": next_order,
                "now": now,
            },
        )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
