"""收录 1589 N · 黄金右脚，保留已有目录内容与统计。

Revision ID: 0093_add_golden_right_foot
Revises: 0092_add_illusion_prototype
Create Date: 2026-10-10
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0093_add_golden_right_foot"
down_revision: str | None = "0092_add_illusion_prototype"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加黄金右脚；已有标识或地址的内容、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 复用现有竞速分类；分类缺失时在插入前终止，不另建分类或更改归属。
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": "racing"}
    )
    if category_id is None:
        raise RuntimeError("0093 requires catalog category racing")

    slug = "1589n-golden-right-foot"
    # 用户已确认保留可用的 HTTP 原址；不改写协议，后台仍沿用现有 HTTPS 校验。
    url = "http://sxyongweb.cn/Brake/index.html"
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
        return

    # 隐藏项目也参与分类末尾排序；空分类从零开始，新项目浏览次数沿用默认值零。
    next_order = int(
        bind.scalar(
            sa.text(
                "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                "WHERE category_id = :category_id"
            ),
            {"category_id": category_id},
        )
    ) + 1
    now = datetime.now(UTC)
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
            "name": "1589 N · 黄金右脚",
            "url": url,
            "description": (
                "第一人称驾驶小游戏，在日落海岸公路上控制刹车力度，"
                "保持 1000–1589 N 完成超车，避免追尾或踏板断裂。"
            ),
            "author_name": "qeeshui",
            "author_url": "https://linux.do/u/qeeshui/summary",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
