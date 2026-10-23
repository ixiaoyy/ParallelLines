"""收录遗迹：破巢，保留已有目录内容与统计。

Revision ID: 0100_add_yiji_pochao
Revises: 0099_add_qunying_zhulu
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0100_add_yiji_pochao"
down_revision: str | None = "0099_add_qunying_zhulu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加遗迹：破巢；已有标识或地址的内容、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 复用现有策略分类；分类缺失时在插入前终止，不另建分类或更改归属。
    category_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"), {"slug": "rts"}
    )
    if category_id is None:
        raise RuntimeError("0100 requires catalog category rts")

    slug = "yiji-pochao"
    url = "https://maya-godot-demo-oct21.adeptllama20.chatgpt.site/"
    https_root = url.rstrip("/")
    http_root = https_root.replace("https://", "http://", 1)
    # 仅将本站根地址的协议、末尾斜线和查询参数视为同一入口，保留隐藏及其他分类记录。
    existing_id = bind.scalar(
        sa.text(
            "SELECT id FROM catalog_projects WHERE slug = :slug "
            "OR destination_url IN (:https_root, :https_slash, :http_root, :http_slash) "
            "OR destination_url LIKE :https_query OR destination_url LIKE :https_slash_query "
            "OR destination_url LIKE :http_query OR destination_url LIKE :http_slash_query LIMIT 1"
        ),
        {
            "slug": slug,
            "https_root": https_root,
            "https_slash": url,
            "http_root": http_root,
            "http_slash": f"{http_root}/",
            "https_query": f"{https_root}?%",
            "https_slash_query": f"{https_root}/?%",
            "http_query": f"{http_root}?%",
            "http_slash_query": f"{http_root}/?%",
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
    # 只追加本游戏目录资料，不创建评分或上传记录，也不改动已有项目。
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
            "name": "遗迹：破巢",
            "url": url,
            "description": (
                "遗迹题材即时战术游戏，指挥小队整备装备、升级移动堡垒，"
                "对抗虫潮并突破母巢防线。"
            ),
            "author_name": "shuishen49",
            "author_url": "https://linux.do/u/shuishen49/summary",
            "sort_order": next_order,
            "now": now,
        },
    )


def downgrade() -> None:
    """仅回退版本号；保留游戏、人工编辑、浏览与评分，撤下使用管理员隐藏入口。"""

    # 收录后的业务数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
