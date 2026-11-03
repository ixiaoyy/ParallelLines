"""收录四款精选网页游戏，保留已有目录内容与统计。

Revision ID: 0102_add_selected_web_games
Revises: 0101_catalog_ai_ratings
Create Date: 2026-11-03
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0102_add_selected_web_games"
down_revision: str | None = "0101_catalog_ai_ratings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加四款外链游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 仅收录已确认的四款作品；合作作品使用完整署名及展示双方署名的作品页。
    projects = (
        (
            "puzzle",
            "gd-spectrum",
            "Spectrum",
            "https://gd.games/mrmeeseeks/spectrum",
            "同步控制红、绿、蓝三名角色穿越平台与机关，利用不同颜色协作解谜；"
            "使用方向键、空格、E 和 R 操作。",
            "Calastrovsk",
            "https://gd.games/Calastrovsk",
        ),
        (
            "stages",
            "gd-fungi-run",
            "Fungi Run",
            "https://gd.games/shehan/fungirun",
            "蘑菇主题无限跑酷，运用二段跳、冲刺与射击躲避障碍并挑战距离，"
            "使用键盘和鼠标操作。",
            "SHEHAN",
            "https://gd.games/SHEHAN",
        ),
        (
            "tower-defense",
            "gd-super-chicken-td",
            "Super Chicken TD",
            "https://gd.games/texugozap/super-chicken-td",
            "布置小鸡防线，抵挡啃食庄稼的虫群，保护农场。",
            "texugozap / Rafa38gh",
            "https://gd.games/texugozap/super-chicken-td",
        ),
        (
            "casual",
            "gd-golf-adventures-2",
            "Golf Adventures! 2",
            "https://gd.games/zachjukamashi/golf-adventures-2",
            "像素风迷你高尔夫，包含 108 个关卡与 5 种主题，调整击球方向和力度完成挑战；"
            "首次加载可能较慢。",
            "ZachjuKamashi / lhphr",
            "https://gd.games/zachjukamashi/golf-adventures-2",
        ),
    )
    # 先核对全部所需分类；任一缺失时在插入前终止，避免只收录部分游戏。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('puzzle', 'stages', 'tower-defense', 'casual')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("puzzle", "stages", "tower-defense", "casual")):
        raise RuntimeError("0102 requires catalog categories puzzle, stages, tower-defense and casual")

    now = datetime.now(UTC)
    for category_slug, slug, name, url, description, author_name, author_url in projects:
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
            continue

        category_id = categories[category_slug]
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

