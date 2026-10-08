"""Add thirteen Astra games while preserving existing entries and statistics.

Revision ID: 0087_add_astra_updates
Revises: 0086_add_external_games
Create Date: 2026-10-08
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0087_add_astra_updates"
down_revision: str | None = "0086_add_external_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加十三个外部游戏；已有标识或地址的人工编辑、隐藏状态和统计不变。"""

    bind = op.get_bind()
    projects = (
        (
            "shooting",
            "hollowmark",
            "HOLLOWMARK",
            "https://hollowmark.mindblown.ai/",
            "第一人称探索工业地下世界，寻找门禁卡、管理弹药并迎战敌人。",
            "Mindblown",
            "https://mindblown.ai/",
        ),
        (
            "shooting",
            "canyon-overdrive",
            "Canyon Overdrive",
            "https://canyonoverdrive.ai-created.com/",
            "驾驶战机穿越霓虹峡谷，以机炮、导弹与滚转突破封锁。",
            "Marco van Hylckama Vlieg / AI & Design",
            "https://x.com/AIandDesign",
        ),
        (
            "stages",
            "flight-1073",
            "Flight 1073",
            "https://flight1073.pages.dev/play/",
            "希伯来语航空恶搞小游戏，躲避餐车、完成限时任务并设法降落。",
            "Guy Eshel",
            "https://x.com/GuyEshel_",
        ),
        (
            "shooting",
            "foe-to-fleet",
            "FOE TO FLEET",
            "https://foe-to-fleet.miya333.chatgpt.site",
            "将击败的敌人收编为舰队，让伙伴协助攻防，撑过七波弹幕进攻。",
            "miya",
            "https://x.com/miya00907380",
        ),
        (
            "action",
            "moxride",
            "MoxRide",
            "https://www.moxride.com/",
            "在彩色城市中下坡滑板，通过磨轨、腾空动作与连续技巧得分。",
            "Moxazza / Moxazza Games",
            "https://www.moxride.com/",
        ),
        (
            "shooting",
            "midway-1942",
            "中途岛海战·空中突击",
            "https://ihca.cn/midway/",
            "与僚机迎战敌机并轰炸航母，掌握重力投弹落点，返回友舰补给。",
            "xilinnihao-afk / 一海千寻的AI实验室",
            "https://github.com/xilinnihao-afk",
        ),
        (
            "shooting",
            "sandline",
            "沙线行动 / SANDLINE",
            "https://ihca.cn/sandline/",
            "与 AI 队友进行单机 3 对 3 战术交战，运用掩体、枪械与手雷争夺爆破目标。",
            "xilinnihao-afk / 一海千寻的AI实验室",
            "https://github.com/xilinnihao-afk",
        ),
        (
            "action",
            "surge-for-oinja",
            "SURGE for Oinja",
            "https://oinja-game.vercel.app/",
            "自动攻击的第三人称生存游戏，组合电气技能和支援机械，修复设施并挑战首领。",
            "Olivia",
            "https://github.com/Olivia295",
        ),
        (
            "action",
            "jellyblob",
            "JellyBlob.win",
            "https://jellyblob.win/",
            "多人果冻竞技场，收集水滴、用尾迹围堵对手并跳跃避险。",
            "kvickan",
            "https://buymeacoffee.com/kvickan",
        ),
        (
            "puzzle",
            "astra-2048-eddy",
            "Astra 2048",
            "https://jianfan.app/2048/gpt/",
            "滑动合并相同数字并挑战 2048，收录作者模型对比中的 Astra 版本。",
            "Eddy",
            "https://x.com/ieddysun",
        ),
        (
            "puzzle",
            "the-fourth-knock",
            "The Fourth Knock",
            "https://nikhilsatishdesai.github.io/the-fourth-knock/play/",
            "探索 Cedar House、询问人物并组合线索，解开 2.5D 密室凶案。",
            "Nikhil Desai",
            "https://x.com/NikhilDesai_007",
        ),
        (
            "action",
            "saber-descent",
            "Saber / Descent",
            "https://vheissu.github.io/saber-battle/",
            "持能量剑探索五层地牢，以连击、格挡和冲刺击败守卫并前进。",
            "Dwayne",
            "https://x.com/CtrlAltDwayne",
        ),
        (
            "stages",
            "sulli-run",
            "Sulli RUN",
            "https://sulli-game.vercel.app/",
            "操控 3D 大猩猩在霓虹城市跑酷，换道、跳跃和滑行躲避障碍得分。",
            "Morteza",
            "https://x.com/Mortezabihzadeh",
        ),
    )
    # 先核对全部现有分类；任一缺失时在插入前终止，避免只收录部分游戏。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('action', 'shooting', 'stages', 'puzzle')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("action", "shooting", "stages", "puzzle")):
        raise RuntimeError("0087 requires catalog categories action, shooting, stages and puzzle")

    now = datetime.now(UTC)
    for category_slug, slug, name, url, description, author_name, author_url in projects:
        # 外部地址有无末尾斜线均视为同一游戏；已有记录的内容、隐藏状态和统计不变。
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

    # 收录后的使用数据不可自动删除，沿用既有游戏迁移的回退约定。
    pass
