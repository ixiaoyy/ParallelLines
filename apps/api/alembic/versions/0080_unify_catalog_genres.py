"""Unify the catalog's 183 reviewed games under fifteen gameplay categories.

Revision ID: 0080_unify_catalog_genres
Revises: 0079_catalog_covers_farming
Create Date: 2026-09-27
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "0080_unify_catalog_genres"
down_revision: str | None = "0079_catalog_covers_farming"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "catalog_genres_20260927.json"


def _load_plan() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """读取已核对的分类快照，返回新分类、原分类和游戏归属；重复或缺项时终止。"""

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    categories = payload["categories"]
    previous = payload["previous_categories"]
    projects = payload["projects"]
    target_slugs = {item["slug"] for item in categories}
    previous_slugs = {item["slug"] for item in previous}
    if (
        len(categories) != 15
        or len(target_slugs) != 15
        or categories[-1]["slug"] != "farming"
        or len(projects) != 183
        or len({item["slug"] for item in projects}) != 183
        or any(item["category"] not in target_slugs for item in projects)
        or any(item["previous_category"] not in previous_slugs for item in projects)
    ):
        raise RuntimeError("0080 catalog classification snapshot is inconsistent")
    return categories, previous, projects


def upgrade() -> None:
    """统一已确认分类，只迁移仍属于快照原分类的游戏，不修改作品及评分内容。"""

    categories, previous, projects = _load_plan()
    bind = op.get_bind()
    now = datetime.now(UTC)
    category_ids = dict(bind.execute(sa.text("SELECT slug, id FROM catalog_categories")).all())

    # 复用稳定分类标识；仅新增动作、角色扮演和模拟经营，种田固定在最后。
    for order, category in enumerate(categories):
        slug = category["slug"]
        if slug not in category_ids:
            bind.execute(
                sa.text(
                    "INSERT INTO catalog_categories "
                    "(slug, name, sort_order, is_visible, created_at, updated_at) "
                    "VALUES (:slug, :name, :sort_order, TRUE, :now, :now)"
                ),
                {**category, "sort_order": order, "now": now},
            )
            category_ids[slug] = bind.scalar(
                sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": slug}
            )
        else:
            bind.execute(
                sa.text(
                    "UPDATE catalog_categories SET name = :name, sort_order = :sort_order, "
                    "is_visible = TRUE, "
                    "updated_at = :now WHERE id = :id"
                ),
                {
                    "id": category_ids[slug],
                    "name": category["name"],
                    "sort_order": order,
                    "now": now,
                },
            )

    # 固定 183 个标识逐条迁移；管理员在快照后另行归类的作品和新投稿不被覆盖。
    for project in projects:
        previous_id = category_ids.get(project["previous_category"])
        if previous_id is None or project["category"] == project["previous_category"]:
            continue
        bind.execute(
            sa.text(
                "UPDATE catalog_projects SET category_id = :category_id, updated_at = :now "
                "WHERE slug = :slug AND category_id = :previous_id"
            ),
            {
                "slug": project["slug"],
                "previous_id": previous_id,
                "category_id": category_ids[project["category"]],
                "now": now,
            },
        )

    # 旧大类只在完全没有作品时隐藏，隐藏作品也计入，避免影响未纳入快照的内容。
    target_slugs = {category["slug"] for category in categories}
    for category in previous:
        if category["slug"] in target_slugs:
            continue
        bind.execute(
            sa.text(
                "UPDATE catalog_categories SET is_visible = FALSE, updated_at = :now "
                "WHERE slug = :slug AND NOT EXISTS "
                "(SELECT 1 FROM catalog_projects WHERE category_id = catalog_categories.id)"
            ),
            {"slug": category["slug"], "now": now},
        )


def downgrade() -> None:
    """回退版本号时保留分类数据，恢复归属需按固定快照核对后单独执行。"""

    # 未保存实际迁移集合，自动回写会覆盖迁移前后人工调整过的归属。
    pass
