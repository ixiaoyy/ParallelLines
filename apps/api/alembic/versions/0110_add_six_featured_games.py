"""追加六款精选网页游戏，保留原目录资料、显隐与评分统计。

Revision ID: 0110_add_six_featured_games
Revises: 0109_birdland_localized_entry
Create Date: 2026-11-10
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa

from alembic import op

revision: str = "0110_add_six_featured_games"
down_revision: str | None = "0109_birdland_localized_entry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """仅追加六款已确认作品；标识或入口已存在时保留原记录，不导入外站分数。"""

    bind = op.get_bind()
    # 原站口碑只作精选线索；玩法、语言和版本边界来自各作者公开作品页。
    projects = (
        (
            "puzzle",
            "dragonsweeper",
            "Dragonsweeper",
            "https://html-classic.itch.zone/html/12786123/index.html",
            "扫雷与地牢探索结合的解谜游戏：观察数字和怪物图鉴，判断怪物位置与强度，"
            "管理生命和升级，逐步探索棋盘。",
            "Daniel Benmergui",
            "https://danielben.itch.io/",
        ),
        (
            "puzzle",
            "growmi",
            "Growmi",
            "https://html-classic.itch.zone/html/7612919/index.html",
            "在相互连接的像素世界中伸展身体、移动与解谜，逐步找回能力并探索新区域；"
            "支持撤销、重开和地图查看。",
            "Carlos Pedroso / Inês Ribeiro",
            "https://carlospedroso.itch.io/",
        ),
        (
            "simulation",
            "sort-the-court",
            "Sort the Court!",
            "https://html-classic.itch.zone/html/347310/index.html",
            "英文王国决策经营游戏：回应来访者的请求，在金钱、人口与幸福之间权衡。"
            "此入口为作者发布的原版网页游戏，手机与其他语言更新版另有入口。",
            "Graeme Borland / amymja / Bogdan Rybak",
            "https://graebor.itch.io/sort-the-court",
        ),
        (
            "cards",
            "solitomb",
            "Solitomb",
            "https://html-classic.itch.zone/html/12290587/index.html",
            "英文接龙地牢游戏：组合牌面攻击怪物，购买协同能力，并管理资源与恶魔的耐心。"
            "此入口为免费 PICO-8 原版，不含另行开发的扩充版内容。",
            "Jakub Wasilewski / Chris Donnelly",
            "https://krajzeg.itch.io/solitomb",
        ),
        (
            "rts",
            "slipways-classic",
            "Slipways Classic",
            "https://html-classic.itch.zone/html/3076366/index.html",
            "英文星际贸易策略游戏：为星球选择产业、连接供需网络并研究科技，发展经济。"
            "此入口为免费 PICO-8 经典版，不含付费扩充版的议会与战役等内容。",
            "Jakub Wasilewski / Gruber",
            "https://krajzeg.itch.io/slipways",
        ),
        (
            "cards",
            "die-in-the-dungeon-classic",
            "Die in the Dungeon CLASSIC",
            "https://html-classic.itch.zone/html/7330268/"
            "Die%20in%20the%20Dungeon%201.6.2f%20%5BWEB%5D/index.html",
            "英文骰子构筑与回合制地牢游戏：组合攻击、防御和强化骰子，"
            "通过战斗与奖励调整构筑。此入口为免费 Classic 旧版网页游戏，非另售商业完整版。",
            "Alarts / SexyBuggy / Jaun / aghsshagahdjjdhwhwureuduu",
            "https://alarts.itch.io/die-in-the-dungeon",
        ),
    )
    # 四个既有分类必须全部就绪；缺失时在首写前终止，不创建或调整分类。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('puzzle', 'simulation', 'cards', 'rts')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("puzzle", "simulation", "cards", "rts")):
        raise RuntimeError(
            "0110 requires catalog categories puzzle, simulation, cards and rts"
        )

    # 本批最多六条；短保存点只包数据库操作，任一插入失败时整批回滚。
    with bind.begin_nested():
        now = datetime.now(UTC)
        for category_slug, slug, name, url, description, author_name, author_url in projects:
            # 防重包含隐藏和跨分类记录；只等价 path 尾斜线，保留 query 与 fragment。
            parts = urlsplit(url)
            path = parts.path.rstrip("/")
            url_without_slash = urlunsplit(parts._replace(path=path))
            url_with_slash = urlunsplit(parts._replace(path=f"{path}/"))
            existing_id = bind.scalar(
                sa.text(
                    "SELECT id FROM catalog_projects WHERE slug = :slug "
                    "OR destination_url IN (:url_without_slash, :url_with_slash) LIMIT 1"
                ),
                {
                    "slug": slug,
                    "url_without_slash": url_without_slash,
                    "url_with_slash": url_with_slash,
                },
            )
            if existing_id is not None:
                continue

            category_id = categories[category_slug]
            # 隐藏作品参与末尾排序；解谜和卡牌的同类两款依次追加，不移动原有项目。
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
    """仅退版本号；不删除游戏或评分，撤下须经授权使用目录后台隐藏。"""

    # 保留新增后的真实评分、浏览和人工维护，不以降版本覆盖后续业务数据。
    pass
