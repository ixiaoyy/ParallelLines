"""Classify catalog projects while preserving admin-managed fields.

Revision ID: 0075_catalog_genres
Revises: 0074_catalog
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0075_catalog_genres"
down_revision: str | None = "0074_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GENRES: tuple[tuple[str, str], ...] = (
    ("shooting", "射击"),
    ("racing", "竞速"),
    ("funny", "搞怪"),
    ("puzzle", "智力"),
    ("casual", "休闲"),
)

# 仅按稳定标识识别首批项目，原来的名称、链接和展示设置可由管理员继续维护。
SEED_PROJECTS: tuple[tuple[str, str], ...] = (
    ("clock-out", "puzzle"),
    ("merge-watermelon", "puzzle"),
    ("qin-imperial-factory", "funny"),
    ("super-mario", "casual"),
    ("csgo-desert", "shooting"),
    ("infinite-garden", "casual"),
    ("fruit-ninja", "casual"),
    ("qq-racing", "racing"),
    ("cf-transport", "shooting"),
    ("pelican-bike", "racing"),
    ("fablespace", "casual"),
    ("generals-soldiers", "puzzle"),
)


def upgrade() -> None:
    """新增五个类型，只调整仍在游戏分类的首批项目归属。"""

    bind = op.get_bind()
    now = datetime.now(UTC)

    # 已有同标识分类可能由管理员创建，保留其名称、图标和显示设置。
    category_ids: dict[str, int] = {}
    for order, (slug, name) in enumerate(GENRES):
        category_id = bind.scalar(
            sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
            {"slug": slug},
        )
        if category_id is None:
            bind.execute(
                sa.text(
                    "INSERT INTO catalog_categories "
                    "(slug, name, sort_order, is_visible, created_at, updated_at) "
                    "VALUES (:slug, :name, :sort_order, TRUE, :now, :now)"
                ),
                {"slug": slug, "name": name, "sort_order": order, "now": now},
            )
            category_id = bind.scalar(
                sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
                {"slug": slug},
            )
        category_ids[slug] = category_id

    games_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
        {"slug": "games"},
    )
    if games_id is not None:
        # 分类由管理员手动调整过时不覆盖；其他项目字段也不参与迁移。
        update_project = sa.text(
            "UPDATE catalog_projects SET category_id = :category_id, updated_at = :now "
            "WHERE slug = :slug AND category_id = :games_id"
        )
        for slug, genre in SEED_PROJECTS:
            bind.execute(
                update_project,
                {
                    "category_id": category_ids[genre],
                    "now": now,
                    "slug": slug,
                    "games_id": games_id,
                },
            )

    # 仅旧名称仍为 FableSpace 时修正游戏名，不影响已自定义名称或分类的项目。
    bind.execute(
        sa.text(
            "UPDATE catalog_projects SET name = :new_name, updated_at = :now "
            "WHERE slug = :slug AND name = :old_name"
        ),
        {"new_name": "朝花夕拾", "old_name": "FableSpace", "slug": "fablespace", "now": now},
    )


def downgrade() -> None:
    """数据迁移无法区分后续管理员编辑；回退版本号时保留现有目录。"""

    # 分类和项目可能已被管理员继续使用，自动回写或删除会丢失这些编辑。
    pass
