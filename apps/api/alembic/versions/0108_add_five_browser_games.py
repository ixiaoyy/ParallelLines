"""收录五款直达网页游戏，并条件修正 BIRDLAND 作者主页。

Revision ID: 0108_add_five_browser_games
Revises: 0107_add_birdland
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa

from alembic import op

revision: str = "0108_add_five_browser_games"
down_revision: str | None = "0107_add_birdland"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """追加五款作品；旧项目仅在原署名与旧作者地址精确匹配时修正作者主页。"""

    bind = op.get_bind()
    # 固定本批直达入口、完整署名与语言/试玩边界，不导入原站评分。
    projects = (
        (
            "romance",
            "her-tears-were-my-light",
            "她的眼泪曾是我的光芒（Her Tears Were My Light）",
            "https://html-classic.itch.zone/html/18220499/index.html?v=1783279519",
            "支持简体中文的恋爱视觉小说：扮演时间，回溯故事节点，尝试帮助空间摆脱孤独；含轻度恐怖元素。免费网页版不含付费下载版的部分额外功能。",
            "NomnomNami / Emmit / LydianChord",
            "https://nomnomnami.itch.io/",
        ),
        (
            "farming",
            "farmhand",
            "Farmhand",
            "https://jeremyckahn.github.io/farmhand/",
            "英文种田经营游戏：购买种子、种植、浇水并出售作物，结合每日变化的市场价格经营农场；可单人游玩，联网模式为可选功能。",
            "Jeremy Kahn / Farmhand contributors",
            "https://jeremyckahn.itch.io/",
        ),
        (
            "horror",
            "exhibit-of-sorrows",
            "Exhibit of Sorrows",
            "https://html-classic.itch.zone/html/14611877/index.html",
            "英文马戏团展馆互动恐怖短篇：探索手绘展品，完成互动并寻找出口；包含心理恐怖、小丑惊吓与伤害表现。",
            "Maxim Tsai (adayofjoy) / Theresa Kao",
            "https://adayofjoy.itch.io/",
        ),
        (
            "romance",
            "known-unknowns",
            "Known Unknowns",
            "https://known.zone/one",
            "英文校园捉鬼与恋爱文字冒险，围绕旧友情、感情纠葛和神秘事件展开。四章完整免费，此入口从第一章开始；阅读量较大，含粗口及药物相关话题。",
            "Brendan Patrick Hennessy / Izzy Marbella",
            "https://bphennessy.com/",
        ),
        (
            "rpg",
            "crosscode-demo",
            "CrossCode（网页试玩版）",
            "https://www.cross-code.com/en/start",
            "英文像素动作角色扮演试玩，结合即时战斗、投球机关与解谜。"
            "此入口为官方旧版网页 Demo，非付费完整版。",
            "Radical Fish Games",
            "https://www.radicalfishgames.com/",
        ),
    )
    # 先核齐四个分类，再进行任何写入，缺分类时不提前修改旧作者地址。
    categories = dict(
        bind.execute(
            sa.text(
                "SELECT slug, id FROM catalog_categories "
                "WHERE slug IN ('romance', 'farming', 'horror', 'rpg')"
            )
        ).all()
    )
    if any(slug not in categories for slug in ("romance", "farming", "horror", "rpg")):
        raise RuntimeError("0108 requires catalog categories romance, farming, horror and rpg")

    # 短保存点覆盖本批旧字段修正及新增记录，后续失败时不留下部分写入。
    with bind.begin_nested():
        # 仅修正原记录的一字段；HEX 避免大小写不敏感排序规则误匹配人工署名或地址。
        bind.execute(
            sa.text(
                "UPDATE catalog_projects SET author_url = :to_url "
                "WHERE slug = :slug AND HEX(author_name) = HEX(:expected_name) "
                "AND HEX(author_url) = HEX(:from_url)"
            ),
            {
                "slug": "birdland",
                "expected_name": "Brendan Patrick Hennessy / Izzy Marbella",
                "from_url": "https://bphennessy.itch.io/birdland",
                "to_url": "https://bphennessy.com/",
            },
        )
        now = datetime.now(UTC)
        for category_slug, slug, name, url, description, author_name, author_url in projects:
            # 仅 path 尾斜线视为等价，完整保留 query，不将斜线拼入版本参数值。
            url_parts = urlsplit(url)
            path_without_slash = url_parts.path.rstrip("/")
            url_without_slash = urlunsplit(url_parts._replace(path=path_without_slash))
            url_with_slash = urlunsplit(url_parts._replace(path=f"{path_without_slash}/"))
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
            # 隐藏项目和本批已插入项目均参与末尾排序，恋爱两款顺序追加。
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
    """仅退版本号；不删作品、评分或反写作者地址，恢复须使用发布前值快照确认。"""

    # 保留新增后的业务数据与后续人工维护，撤下作品使用管理员隐藏入口。
    pass
