"""收录熵刃、NEXUS 与 EmberFall，保留已有目录内容与统计。

Revision ID: 0089_add_three_external_games
Revises: 0088_add_greyfall
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0089_add_three_external_games"
down_revision: str | None = "0088_add_greyfall"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加三款外部游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    projects = (
        (
            "action",
            "entropy-blade",
            "熵刃 · ENTROPY BLADE",
            "https://game.inc.re/entropy-blade/",
            "像素风横版动作肉鸽，包含三名角色、武技连段与秘技，"
            "四个场景各有专属敌人与首领，支持键盘、手柄和手机触屏。",
            "mumuhaha487",
            "https://linux.do/u/mumuhaha487/summary",
        ),
        (
            "exploration",
            "nexus",
            "NEXUS",
            "https://traveritas.github.io/nexus/",
            "第一人称探索游戏，从家中出发，通过门、杯子与床穿行于不同世界，"
            "使用罗盘查看地图，在日记中记录足迹。",
            "traveritas",
            "https://linux.do/u/traveritas/summary",
        ),
        (
            "action",
            "emberfall",
            "EmberFall",
            "https://ef.usbsb.sbs/",
            "暗黑像素风生存动作游戏，选择近战、远程或法术猎人，通过走位、冲刺和装备构筑"
            "抵御三十波敌潮，随后可继续无尽狩猎，支持键鼠与手机触屏。",
            "doveusa",
            "https://linux.do/u/doveusa/summary",
        ),
    )
    # 先核对全部所需分类；任一缺失时在插入前终止，避免只收录部分游戏。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('action', 'exploration')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("action", "exploration")):
        raise RuntimeError("0089 requires catalog categories action and exploration")

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
        # 隐藏条目也参与分类末尾排序；同分类逐项追加，浏览次数沿用默认值零。
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
