"""追加三款网页游戏外链，不修改既有目录资料和评分。

Revision ID: 0115_add_three_browser_games
Revises: 0114_add_four_browser_games
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa

from alembic import op

revision: str = "0115_add_three_browser_games"
down_revision: str | None = "0114_add_four_browser_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """在现有分类末尾追加三款游戏；跳过已存在的标识或入口。"""

    bind = op.get_bind()
    # 原作与社区译本分别署名，只收录网页入口，不导入外站评分。
    projects = (
        (
            "simulation",
            "sandspiel",
            "Sandspiel",
            "https://sandspiel.club/",
            "在像素画布上撒沙、引水、种植物，观察材料如何流动和相互作用。"
            "没有固定关卡，可以从空白画布开始。",
            "Max Bittker",
            "https://maxbittker.com/",
        ),
        (
            "casual",
            "we-become-what-we-behold",
            "我们变成了我们所看到的",
            "https://claycoffee.github.io/wbwwb/",
            "用相机拍下街上的瞬间，看报道如何改变人群的行为。"
            "这是 We Become What We Behold 的社区简中版，约 5 分钟，含卡通暴力及血腥画面。",
            "Nicky Case（原作） / ClayCoffee（简中译版）",
            "https://ncase.itch.io/wbwwb",
        ),
        (
            "puzzle",
            "net-puzzle",
            "Net（旋转接线）",
            "https://www.chiark.greenend.org.uk/~sgtatham/puzzles/js/net.html",
            "转动方格里的接线，让所有节点连成一张没有闭环的网络。"
            "英文网页，可用鼠标或键盘旋转方格。",
            "Simon Tatham",
            "https://www.chiark.greenend.org.uk/~sgtatham/puzzles/",
        ),
    )
    # 前置分类缺失时整批停止，不自行创建或改动现有分类。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('simulation', 'casual', 'puzzle')"
            )
        ).all()
    )
    if len(categories) != 3:
        raise RuntimeError("0115 requires catalog categories simulation, casual and puzzle")

    # 同批写入使用保存点，避免中途失败后留下部分新记录。
    with bind.begin_nested():
        now = datetime.now(UTC)
        for category_slug, slug, name, url, description, author_name, author_url in projects:
            # 查重包含隐藏项目；只折叠路径尾斜线，不去掉参数或片段。
            parts = urlsplit(url)
            path = parts.path.rstrip("/")
            existing_id = bind.scalar(
                sa.text(
                    "SELECT id FROM catalog_projects WHERE slug = :slug "
                    "OR destination_url IN (:url_without_slash, :url_with_slash) LIMIT 1"
                ),
                {
                    "slug": slug,
                    "url_without_slash": urlunsplit(parts._replace(path=path)),
                    "url_with_slash": urlunsplit(parts._replace(path=f"{path}/")),
                },
            )
            if existing_id is not None:
                continue

            category_id = categories[category_slug]
            # 隐藏项目也占原排序；新条目沿用零浏览默认值，不写评分表。
            next_order = int(
                bind.scalar(
                    sa.text(
                        "SELECT COALESCE(MAX(sort_order), -1) FROM catalog_projects "
                        "WHERE category_id = :category_id"
                    ),
                    {"category_id": category_id},
                )
            ) + 1
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
    """仅回退迁移版本；需要下架时经授权在目录后台隐藏。"""

    # 不删除已开始累积的浏览、评分或人工维护数据。
    pass
