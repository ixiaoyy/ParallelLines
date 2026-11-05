"""收录四款网页游戏，保留已有目录内容与统计。

Revision ID: 0103_add_more_web_games
Revises: 0102_add_selected_web_games
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0103_add_more_web_games"
down_revision: str | None = "0102_add_selected_web_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加四款外链游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 只记录原站已确认的玩法与署名；合作作品链接到展示完整署名的作品页。
    projects = (
        (
            "simulation",
            "gd-helicopter-sos",
            "Helicopter SOS",
            "https://gd.games/malaspina/helicopter-sos",
            "操纵直升机机械臂救起落水者，逐关完成救援挑战；支持键盘、鼠标与触控。",
            "Malaespina",
            "https://gd.games/Malaespina",
        ),
        (
            "racing",
            "gd-rocket-racers",
            "Rocket Racers",
            "https://gd.games/tulenvakiproductions/rocket-racers",
            "在陨石带驾驶飞船避开障碍，利用加减速道具挑战不断提升的速度；"
            "支持键盘、鼠标与触控。",
            "TulenvakiProductions",
            "https://gd.games/TulenvakiProductions",
        ),
        (
            "puzzle",
            "itch-six-cats-under",
            "Six Cats Under",
            "https://teambeanloop.itch.io/six-cats-under",
            "扮演幽灵，利用有限的念力影响房间里的物品，解开机关，帮助猫咪逃出公寓。",
            "Team Bean Loop / Mosu",
            "https://teambeanloop.itch.io/six-cats-under",
        ),
        (
            "simulation",
            "itch-the-final-earth-2",
            "The Final Earth 2",
            "https://flori9.itch.io/the-final-earth-2",
            "在太空中收集资源、建造并发展垂直城市。此入口为网页基础版；"
            "Steam 与手机扩展版另售。",
            "Florian van Strien",
            "https://flori9.itch.io",
        ),
    )
    # 先核齐本批全部分类；缺少任一分类时在插入前终止，避免部分收录。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('simulation', 'racing', 'puzzle')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("simulation", "racing", "puzzle")):
        raise RuntimeError("0103 requires catalog categories simulation, racing and puzzle")

    now = datetime.now(UTC)
    for category_slug, slug, name, url, description, author_name, author_url in projects:
        # 隐藏、跨分类记录同样防重；外链仅有末尾斜线差异时视为同一作品。
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
        # 隐藏条目和本批已插入作品均参与末尾排序；新浏览次数沿用默认值零。
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
