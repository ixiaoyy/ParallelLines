"""将三款作品改为已核实直达入口，隐藏九款待确认作品，保留原记录及统计。

Revision ID: 0105_catalog_direct_entries
Revises: 0104_add_classic_web_games
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0105_catalog_direct_entries"
down_revision: str | None = "0104_add_classic_web_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIRECT_ENTRIES = (
    (
        "gd-spectrum",
        "https://gd.games/mrmeeseeks/spectrum",
        "https://html-classic.itch.zone/html/7294044/Spectrum%201.1/index.html?v=1782787944",
    ),
    (
        "itch-six-cats-under",
        "https://teambeanloop.itch.io/six-cats-under",
        "https://html-classic.itch.zone/html/2267583/index.html",
    ),
    (
        "itch-the-final-earth-2",
        "https://flori9.itch.io/the-final-earth-2",
        "https://html-classic.itch.zone/html/1995721-336862/index.html",
    ),
)
HIDDEN_SLUGS = (
    "gd-fungi-run",
    "gd-super-chicken-td",
    "gd-golf-adventures-2",
    "gd-helicopter-sos",
    "gd-rocket-racers",
    "astra-940973d6b1805a52c1f0",
    "astra-ca4e89010438edf3221e",
    "astra-0a5696802efe2cf4eb0b",
    "astra-0751dc4e0b9b7bc13c1f",
)


def upgrade() -> None:
    """只改指定入口或可见性；目标缺失、人工入口不明或并发改写时整批终止。"""

    bind = op.get_bind()
    target_slugs = tuple(entry[0] for entry in DIRECT_ENTRIES) + HIDDEN_SLUGS
    # 首写前一次齐查十二款；使用各环境实际主键，不新增或删除项目。
    rows = {
        row["slug"]: row
        for row in bind.execute(
            sa.text(
                "SELECT id, slug, destination_url, is_visible FROM catalog_projects "
                "WHERE slug IN :slugs"
            ).bindparams(sa.bindparam("slugs", expanding=True)),
            {"slugs": target_slugs},
        ).mappings()
    }
    missing = [slug for slug in target_slugs if slug not in rows]
    if missing:
        raise RuntimeError(f"0105 missing catalog projects: {', '.join(missing)}")

    # 已是本批直达地址可重跑；除此之外只接受原地址的末尾斜线差异，不覆盖人工改址。
    for slug, original_url, direct_url in DIRECT_ENTRIES:
        current_url = rows[slug]["destination_url"]
        if current_url != direct_url and current_url.rstrip("/") != original_url.rstrip("/"):
            raise RuntimeError(f"0105 refuses unexpected destination_url for: {slug}")

    # 短保存点仅包本批写入；任一 CAS 或 SQL 失败时回滚已改项目，不提交外层迁移事务。
    with bind.begin_nested():
        for slug, _original_url, direct_url in DIRECT_ENTRIES:
            row = rows[slug]
            if row["destination_url"] == direct_url:
                continue
            # HEX 精确比较 URL 字节，避免大小写不敏感的数据库排序规则掩盖并发人工改址。
            result = bind.execute(
                sa.text(
                    "UPDATE catalog_projects SET destination_url = :direct_url "
                    "WHERE id = :id AND slug = :slug "
                    "AND HEX(destination_url) = HEX(:previous_url)"
                ),
                {
                    "direct_url": direct_url,
                    "id": row["id"],
                    "slug": slug,
                    "previous_url": row["destination_url"],
                },
            )
            if result.rowcount != 1:
                raise RuntimeError(f"0105 concurrent catalog change for: {slug}")

        for slug in HIDDEN_SLUGS:
            row = rows[slug]
            if not row["is_visible"]:
                continue
            # 已隐藏的项目保持原样；其余只置隐藏，不改旧入口、时间、封面或统计。
            result = bind.execute(
                sa.text(
                    "UPDATE catalog_projects SET is_visible = FALSE "
                    "WHERE id = :id AND slug = :slug AND is_visible = :previous_visibility"
                ),
                {
                    "id": row["id"],
                    "slug": slug,
                    "previous_visibility": row["is_visible"],
                },
            )
            if result.rowcount != 1:
                raise RuntimeError(f"0105 concurrent catalog change for: {slug}")


def downgrade() -> None:
    """仅退版本号；不自动重展或覆盖人工入口，恢复须使用发布前值快照单独确认。"""

    # 项目 ID、评分及浏览量保留；自动回写旧入口或重新展示可能覆盖后续人工维护。
    pass
