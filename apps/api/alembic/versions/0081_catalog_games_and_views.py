"""Add catalog view counts and liangdabiao's two poetry games.

Revision ID: 0081_catalog_games_and_views
Revises: 0080_unify_catalog_genres
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0081_catalog_games_and_views"
down_revision: str | None = "0080_unify_catalog_genres"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTHOR_NAME = "liangdabiao"
AUTHOR_URL = "https://linux.do/u/liangdabiao/summary"
PROJECTS = (
    (
        "shi-yu-yuanfang",
        "诗与远方",
        "rts",
        "https://gushi.348349.xyz/",
        "在十五回合的诗人生涯中，权衡银两、粮食、名声、体魄、诗兴与人脉。",
    ),
    (
        "hongloumeng-haitang-shishe",
        "红楼梦-海棠诗社",
        "cards",
        "https://hlm.348349.xyz/",
        "与红楼人物四人围桌，用诗句手牌接龙，可自创诗句并通过评诗积累积分。",
    ),
)


def upgrade() -> None:
    """新增打开计数及两款游戏；标识或根网址已收录时保留管理员现有记录。"""

    bind = op.get_bind()
    now = datetime.now(UTC)
    category_ids = {}
    next_orders = {}

    # 复用现有策略和卡牌分类；先检查全部前置分类，避免缺失时只写入部分游戏。
    for genre in ("rts", "cards"):
        category_id = bind.scalar(
            sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": genre}
        )
        if category_id is None:
            raise RuntimeError(f"0081 requires catalog category {genre}")
        category_ids[genre] = category_id
        next_orders[genre] = int(
            bind.scalar(
                sa.text(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
        ) + 1

    # MySQL 的 DDL 会独立提交；列存在时跳过，允许数据写入失败后重新执行同一迁移。
    columns = {column["name"] for column in sa.inspect(bind).get_columns("catalog_projects")}
    if "view_count" not in columns:
        op.add_column(
            "catalog_projects",
            sa.Column("view_count", sa.BigInteger(), nullable=False, server_default="0"),
        )

    for slug, name, genre, url, description in PROJECTS:
        # 两个地址均为站点根地址，带或不带末尾斜线视为同一入口；不覆盖已有内容。
        url_without_slash = url.rstrip("/")
        candidates = bind.execute(
            sa.text(
                "SELECT slug, destination_url FROM catalog_projects "
                "WHERE slug = :slug OR destination_url IN (:url, :url_without_slash)"
            ),
            {"slug": slug, "url": url, "url_without_slash": url_without_slash},
        ).mappings()
        if any(
            row["slug"] == slug or row["destination_url"] in {url, url_without_slash}
            for row in candidates
        ):
            continue

        # 新游戏追加到对应分类末尾，作者名称和主页使用用户明确提供的信息。
        bind.execute(
            sa.text(
                "INSERT INTO catalog_projects "
                "(category_id, slug, name, destination_url, destination_kind, description, "
                "author_name, author_url, sort_order, is_visible, created_at, updated_at) "
                "VALUES (:category_id, :slug, :name, :url, 'external', :description, "
                ":author_name, :author_url, :sort_order, TRUE, :now, :now)"
            ),
            {
                "category_id": category_ids[genre],
                "slug": slug,
                "name": name,
                "url": url,
                "description": description,
                "author_name": AUTHOR_NAME,
                "author_url": AUTHOR_URL,
                "sort_order": next_orders[genre],
                "now": now,
            },
        )
        next_orders[genre] += 1


def downgrade() -> None:
    """回退计数字段并丢弃打开次数；保留游戏、人工编辑和后续评分。"""

    # 两款游戏沿用目录数据的保留约定，只移除本次新增的统计列。
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("catalog_projects")
    }
    if "view_count" in columns:
        op.drop_column("catalog_projects", "view_count")
