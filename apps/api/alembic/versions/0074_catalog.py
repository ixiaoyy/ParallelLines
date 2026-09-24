"""Create the project catalog and one-time guest ratings.

Revision ID: 0074_catalog
Revises: 0073_classify_seeded_personas
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0074_catalog"
down_revision: str | None = "0073_classify_seeded_personas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 首批项目只在新表创建时写入一次，后续目录内容由管理员维护。
INITIAL_PROJECTS: tuple[tuple[str, str, str, str], ...] = (
    ("clock-out", "准点下班", "https://clockout-18.vercel.app/", "external"),
    (
        "merge-watermelon",
        "合成大西瓜",
        "https://melon-game.jack-514.chatgpt.site/",
        "external",
    ),
    (
        "qin-imperial-factory",
        "秦始皇打螺丝",
        "https://qin-imperial-factory-221.xyjwyf123.chatgpt.site/",
        "external",
    ),
    (
        "super-mario",
        "超级马里奥",
        "https://mushroom-arcade-0905.jumaomaomaoju.chatgpt.site/",
        "external",
    ),
    (
        "csgo-desert",
        "CSGO ·沙漠行动",
        "https://dust-ii-map.yelin8130.chatgpt.site/",
        "external",
    ),
    (
        "infinite-garden",
        "无限庭院",
        "https://infinite-garden.yelin8130.chatgpt.site/",
        "external",
    ),
    (
        "fruit-ninja",
        "水果忍者",
        "https://fruit-ninja-dojo-20260905.yongqixue666.chatgpt.site/",
        "external",
    ),
    (
        "qq-racing",
        "QQ飞车",
        "https://lf3-static.bytednsdoc.com/obj/eden-cn/nulojnulwlo/qqfeiche3d/index.html",
        "external",
    ),
    (
        "cf-transport",
        "穿越火线之运输船",
        "https://lf3-static.bytednsdoc.com/obj/eden-cn/nulojnulwlo/cf-transport-ship/transport-ship.html",
        "external",
    ),
    (
        "pelican-bike",
        "鹈鹕骑自行车",
        "https://lf3-static.bytednsdoc.com/obj/eden-cn/nulojnulwlo/pelican-bike/index.html",
        "external",
    ),
    ("fablespace", "FableSpace", "https://fable.pingxingxian.space/", "external"),
    ("generals-soldiers", "将军战小兵", "/play/generals-soldiers", "internal"),
)


def upgrade() -> None:
    """创建分类、项目和评分表，并导入已确认的游戏入口。"""

    op.create_table(
        "catalog_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "icon_upload_id", sa.BigInteger(), sa.ForeignKey("uploads.id", ondelete="SET NULL")
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_catalog_categories_slug"),
    )
    op.create_index(
        "ix_catalog_categories_visible_order",
        "catalog_categories",
        ["is_visible", "sort_order"],
    )
    op.create_table(
        "catalog_projects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("catalog_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("destination_url", sa.String(length=2048), nullable=False),
        sa.Column("destination_kind", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=300)),
        sa.Column(
            "icon_upload_id", sa.BigInteger(), sa.ForeignKey("uploads.id", ondelete="SET NULL")
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "destination_kind IN ('external', 'internal')",
            name="ck_catalog_projects_destination_kind",
        ),
        sa.UniqueConstraint("slug", name="uq_catalog_projects_slug"),
    )
    op.create_index(
        "ix_catalog_projects_category_visible_order",
        "catalog_projects",
        ["category_id", "is_visible", "sort_order"],
    )
    op.create_table(
        "catalog_ratings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("catalog_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_catalog_ratings_score"),
        sa.UniqueConstraint("project_id", "ip_digest", name="uq_catalog_ratings_project_ip"),
    )
    op.create_index("ix_catalog_ratings_project", "catalog_ratings", ["project_id"])

    bind = op.get_bind()
    now = datetime.now(UTC)
    bind.execute(
        sa.text(
            "INSERT INTO catalog_categories "
            "(slug, name, sort_order, is_visible, created_at, updated_at) "
            "VALUES (:slug, :name, 0, 1, :created_at, :updated_at)"
        ),
        {"slug": "games", "name": "游戏", "created_at": now, "updated_at": now},
    )
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": "games"}
    )
    bind.execute(
        sa.text(
            "INSERT INTO catalog_projects "
            "(category_id, slug, name, destination_url, destination_kind, sort_order, "
            "is_visible, created_at, updated_at) "
            "VALUES (:category_id, :slug, :name, :url, :kind, :sort_order, "
            "1, :created_at, :updated_at)"
        ),
        [
            {
                "category_id": category_id,
                "slug": slug,
                "name": name,
                "url": url,
                "kind": kind,
                "sort_order": order,
                "created_at": now,
                "updated_at": now,
            }
            for order, (slug, name, url, kind) in enumerate(INITIAL_PROJECTS)
        ],
    )


def downgrade() -> None:
    """删除本版新增三表；此操作会永久丢失目录和评分数据。"""

    op.drop_index("ix_catalog_ratings_project", table_name="catalog_ratings")
    op.drop_table("catalog_ratings")
    op.drop_index("ix_catalog_projects_category_visible_order", table_name="catalog_projects")
    op.drop_table("catalog_projects")
    op.drop_index("ix_catalog_categories_visible_order", table_name="catalog_categories")
    op.drop_table("catalog_categories")
