"""将仍使用原站入口的 BIRDLAND 改为站内汉化版，保留既有项目与统计。

Revision ID: 0109_birdland_localized_entry
Revises: 0108_add_five_browser_games
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0109_birdland_localized_entry"
down_revision: str | None = "0108_add_five_browser_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_DESCRIPTION = (
    "英文文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
    "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
)
NEW_DESCRIPTION = (
    "中文汉化文字互动剧情：少女 Bridget 在夏令营中暗恋女孩 Bell，"
    "在奇幻梦境与日常交流间探索感情和自我认同；包含粗口与成熟话题。"
)
GAME_URL = "/games/birdland/index.html"


def upgrade() -> None:
    """仅替换原英文外链；无原记录或人工入口时不写入，目标被占用则终止。"""

    bind = op.get_bind()
    # 使用同一项目 ID 接入汉化版；精确匹配避免覆盖大小写不同的人工标识与入口。
    project = bind.execute(
        sa.text(
            "SELECT id, destination_url, destination_kind FROM catalog_projects "
            "WHERE HEX(slug) = HEX(:slug) LIMIT 1"
        ),
        {"slug": "birdland"},
    ).mappings().first()
    if (
        project is None
        or project["destination_kind"] != "external"
        or project["destination_url"] not in ("https://birdland.camp", "https://birdland.camp/")
    ):
        return

    # 隐藏和跨分类记录也参与入口冲突检查；不覆盖或合并其他项目及其统计。
    relative_urls = (GAME_URL, f"{GAME_URL}/", "/games/birdland/", "/games/birdland")
    target_urls = relative_urls + tuple(
        f"https://pingxingxian.space{url}" for url in relative_urls
    )
    conflict_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE id <> :project_id "
            "AND destination_url IN :target_urls LIMIT 1"
        ).bindparams(sa.bindparam("target_urls", expanding=True)),
        {"project_id": project["id"], "target_urls": target_urls},
    )
    if conflict_id is not None:
        raise RuntimeError("0109 birdland localized destination is already used by another project")

    # 单次条件更新保留人工并发改动；只替换原默认简介，其余资料、显隐和评分均不变。
    bind.execute(
        sa.text(
            "UPDATE catalog_projects SET destination_url = :new_url, "
            "destination_kind = 'internal', description = CASE "
            "WHEN HEX(description) = HEX(:old_description) THEN :new_description "
            "ELSE description END "
            "WHERE id = :project_id AND HEX(slug) = HEX(:slug) "
            "AND HEX(destination_kind) = HEX(:old_kind) "
            "AND HEX(destination_url) = HEX(:old_url)"
        ),
        {
            "project_id": project["id"],
            "slug": "birdland",
            "old_kind": "external",
            "old_url": project["destination_url"],
            "new_url": GAME_URL,
            "old_description": OLD_DESCRIPTION,
            "new_description": NEW_DESCRIPTION,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留入口、人工资料和统计，恢复原站入口须另行定向授权。"""

    # 沿用既有目录迁移的数据保留约定，不自动撤回人工已使用的入口或汉化简介。
    pass
