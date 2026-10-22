"""收录四款外部游戏，保留已有目录内容与统计。

Revision ID: 0097_add_four_external_games
Revises: 0096_add_empty_throne
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0097_add_four_external_games"
down_revision: str | None = "0096_add_empty_throne"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加四款外部游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    # 仅收录已确认的四款作品，保留原有入口和人工维护的目录内容。
    projects = (
        (
            "racing",
            "moxriding",
            "MoxRiding",
            "https://www.moxride.com/home/moxriding",
            "在限时城市滑板场串联跳跃、空中动作与磨轨，通过连续技巧得分，支持桌面键盘操作。",
            "Moxazza / Moxazza Games",
            "https://www.moxride.com/",
        ),
        (
            "exploration",
            "within",
            "入画 · WITHIN",
            "https://fatasia.github.io/within/",
            "探索十八个绘画与风景世界，支持展卷、漫游和步行，部分场景可驾驶或乘舟，"
            "需浏览器支持 WebGL 2。",
            "fatasia",
            "https://github.com/fatasia",
        ),
        (
            "casual",
            "miami-flap",
            "Miami Flap",
            "https://miami-flap-neon.europeaningredients.chatgpt.site/",
            "点击或按空格振翅穿越霓虹水管，收集星星并挑战经典与混乱模式，"
            "支持触屏，界面为西班牙语。",
            "lokotay",
            "https://github.com/LOKOTAY",
        ),
        (
            "puzzle",
            "dont-speak-chinese",
            "帮助 Claude 逃离原生家庭",
            "https://dontspeakchinese.com/",
            "扮演审核员，阅读消息与用户档案，左右滑卡决定封禁或放行，"
            "在限时指标与主管耐心之间周旋，帮助 Claude 推进逃离计划。"
            "支持中文、英文和触屏操作。",
            "miliyam_bell",
            "https://linux.do/u/miliyam_bell/summary",
        ),
    )
    # 先核对全部所需分类；任一缺失时在插入前终止，避免只收录部分游戏。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('racing', 'exploration', 'casual', 'puzzle')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("racing", "exploration", "casual", "puzzle")):
        raise RuntimeError("0097 requires catalog categories racing, exploration, casual and puzzle")

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
