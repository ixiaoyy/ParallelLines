"""Add catalog genres and projects without changing managed entries.

Revision ID: 0076_catalog_card_game
Revises: 0075_catalog_genres
Create Date: 2026-09-25
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0076_catalog_card_game"
down_revision: str | None = "0075_catalog_genres"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_CATEGORIES: tuple[tuple[str, str, int], ...] = (
    ("cards", "卡牌", 5),
    ("romance", "恋爱", 6),
    ("stages", "闯关", 7),
    ("tower-defense", "塔防", 8),
    ("horror", "恐怖", 9),
    ("exploration", "探索", 10),
    ("rts", "即时战略", 11),
)

# 项目链接和分类来自已确认的目录清单；简介仅写对应类型，不推断具体玩法。
NEW_PROJECTS: tuple[tuple[str, str, str, str, str, int], ...] = (
    (
        "yu-gi-oh-destiny-duel",
        "游戏王",
        "cards",
        "https://yu-gi-oh-destiny-duel.pages.dev/",
        "卡牌对战",
        0,
    ),
    (
        "secondhand-3c-store",
        "二手3C店",
        "romance",
        "https://3c.cfnav.me/",
        "恋爱",
        0,
    ),
    (
        "voxel-tides",
        "体素潮汐",
        "casual",
        "https://voxel-tides.vercel.app/",
        "休闲",
        0,
    ),
    (
        "sneaky-thief",
        "Sneaky Thief",
        "stages",
        "https://sneaky-thief.vercel.app/",
        "闯关",
        0,
    ),
    (
        "liuxin-watermelon",
        "流心西瓜",
        "casual",
        "https://game-dxg.pages.dev/",
        "休闲",
        1,
    ),
    (
        "xing-lei-shou-wei",
        "星垒守卫",
        "tower-defense",
        "https://game-xlsw.pages.dev/",
        "塔防",
        0,
    ),
    (
        "yongyao-crystal-tower",
        "永耀晶塔",
        "tower-defense",
        "https://game.tcmiku.cc.cd/",
        "塔防",
        1,
    ),
    (
        "zhi-guai-lu",
        "志怪录",
        "cards",
        "https://game-zgl.pages.dev/",
        "卡牌",
        1,
    ),
    (
        "sanguo-zhengshi",
        "三国争势",
        "cards",
        "https://sanguo-zhengshi-playtest-vdczcfej.edgeone.cool/",
        "卡牌",
        2,
    ),
    (
        "yeyu-tanglou",
        "夜雨唐楼",
        "horror",
        "https://ai.apiuse.cn/game/one/",
        "恐怖",
        0,
    ),
    (
        "non-euclidean-lab",
        "非欧空间实验室",
        "exploration",
        "https://non-euclidean-lab.sworld233.chatgpt.site/",
        "探索",
        0,
    ),
    (
        "geodesic-explorer",
        "测地线",
        "exploration",
        "https://dream-bold-bird-lotus.grok.me/",
        "探索",
        1,
    ),
    (
        "hyperbolic-room",
        "双曲房间",
        "exploration",
        "https://nmgcfudpyu2sm.ok.kimi.link/",
        "探索",
        2,
    ),
    (
        "encounter-command-console",
        "遭遇战指挥台",
        "rts",
        "https://zupu.xxbai.site/",
        "即时战略",
        0,
    ),
)


def upgrade() -> None:
    """按固定标识补入分类和项目，不覆盖后台已有记录。"""

    bind = op.get_bind()
    now = datetime.now(UTC)

    select_category = sa.text("SELECT id FROM catalog_categories WHERE slug = :slug")
    casual_id = bind.scalar(select_category, {"slug": "casual"})
    if casual_id is None:
        # 休闲分类应由上一版迁移提供；缺失时停止，避免把项目挂到错误分类。
        raise RuntimeError("0076 requires catalog category 'casual' from 0075_catalog_genres")

    category_ids = {"casual": casual_id}
    insert_category = sa.text(
        "INSERT INTO catalog_categories "
        "(slug, name, sort_order, is_visible, created_at, updated_at) "
        "VALUES (:slug, :name, :sort_order, TRUE, :now, :now)"
    )
    for slug, name, sort_order in NEW_CATEGORIES:
        category_id = bind.scalar(select_category, {"slug": slug})
        if category_id is None:
            # 同标识分类可能由管理员创建；仅缺失时插入，不覆盖现有设置。
            bind.execute(
                insert_category,
                {"slug": slug, "name": name, "sort_order": sort_order, "now": now},
            )
            category_id = bind.scalar(select_category, {"slug": slug})
        if category_id is None:
            # 新分类必须取得主键，才能把后续项目挂到正确分类。
            raise RuntimeError(f"catalog category {slug!r} has no id after insert")
        category_ids[slug] = category_id

    select_project = sa.text("SELECT id FROM catalog_projects WHERE slug = :slug")
    insert_project = sa.text(
        "INSERT INTO catalog_projects "
        "(category_id, slug, name, destination_url, destination_kind, "
        "description, sort_order, is_visible, created_at, updated_at) "
        "VALUES (:category_id, :slug, :name, :url, :kind, "
        ":description, :sort_order, TRUE, :now, :now)"
    )
    for slug, name, genre, url, description, sort_order in NEW_PROJECTS:
        project_id = bind.scalar(select_project, {"slug": slug})
        if project_id is None:
            # 同标识项目已由管理员维护时，不改其分类、链接或其他展示字段。
            bind.execute(
                insert_project,
                {
                    "category_id": category_ids[genre],
                    "slug": slug,
                    "name": name,
                    "url": url,
                    "kind": "external",
                    "description": description,
                    "sort_order": sort_order,
                    "now": now,
                },
            )


def downgrade() -> None:
    """回退版本号时保留目录数据；需要撤下时由管理员在后台隐藏。"""

    # 无法区分迁移后由管理员修改过的分类和项目，自动删除会丢失这些编辑。
    pass
