"""追加四款直达网页游戏，不修改既有目录资料和评分。

Revision ID: 0114_add_four_browser_games
Revises: 0113_cross_site_traffic
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa

from alembic import op

revision: str = "0114_add_four_browser_games"
down_revision: str | None = "0113_cross_site_traffic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """在既有分类末尾追加四款外链；遇到已存在的标识或入口时跳过。"""

    bind = op.get_bind()
    # 保留网页版本和语言的明确入口；中文译者与原作分开署名，不导入外站评分。
    projects = (
        (
            "racing",
            "polytrack",
            "PolyTrack",
            "https://www.kodub.com/apps/polytrack",
            "支持简体中文的低多边形计时竞速游戏。穿过回环、跃过跳台，反复挑战自己的用时；"
            "也可以用编辑器自制赛道。",
            "Kodub",
            "https://www.kodub.com/",
        ),
        (
            "shooting",
            "space-huggers",
            "Space Huggers",
            "https://killedbyapixel.github.io/SpaceHuggers/",
            "英文像素横版射击游戏：穿行于随机生成的关卡，利用翻滚和可破坏的地形绕开敌人，"
            "用雷达寻找剩余目标。支持单人游玩和手柄本地合作。",
            "Frank Force（KilledByAPixel）",
            "https://frankforce.com/",
        ),
        (
            "rpg",
            "a-dark-room",
            "小黑屋（A Dark Room）",
            "https://adarkroom.doublespeakgames.com/?lang=zh_cn",
            "从在黑屋里点火开始，逐步解锁采集、制作和探索。"
            "本入口是支持简体中文的免费文字冒险原版，不是另售的移植版。",
            "Michael Townsend / doublespeak games",
            "https://doublespeakgames.com/",
        ),
        (
            "rts",
            "evolution-of-trust",
            "信任的进化",
            "https://dccxi.com/trust/",
            "在一轮轮互动中选择合作或欺骗，观察不同策略如何改变收益；"
            "之后可调整规则看合作如何演变。此入口为社区简体中文译版。",
            "Nicky Case（原作） / 吴桐、唐鳳（简中译版署名）",
            "https://ncase.me/",
        ),
    )
    # 分类未齐就终止，不能把部分作品挂入其他分类或更改线上分类。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('racing', 'shooting', 'rpg', 'rts')"
            )
        ).all()
    )
    if len(categories) != 4:
        raise RuntimeError("0114 requires catalog categories racing, shooting, rpg and rts")

    # 四条记录在同一保存点内处理；中途失败时本批不留下部分新增数据。
    with bind.begin_nested():
        now = datetime.now(UTC)
        for category_slug, slug, name, url, description, author_name, author_url in projects:
            # 全目录防重（含隐藏记录）；只折叠路径尾斜线，保留语言参数和片段。
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
            # 隐藏项目也参与末尾排序；新项目沿用零浏览默认值，不写评分表。
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
    """仅退版本号；需要撤下时用目录后台隐藏，不删除访问后的业务数据。"""

    # 保留真实评分、浏览和人工编辑；不因回滚迁移覆盖后续维护。
    pass
