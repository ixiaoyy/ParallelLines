"""Add anonymous submission covers and the farming catalog category.

Revision ID: 0079_catalog_covers_farming
Revises: 0078_import_awesome_astra
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0079_catalog_covers_farming"
down_revision: str | None = "0078_import_awesome_astra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保存待审投稿封面，并在未人工调整时将朝花夕拾归到种田。"""

    op.alter_column("uploads", "user_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column(
        "catalog_submissions",
        sa.Column(
            "cover_upload_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "uploads.id", name="fk_catalog_submissions_cover_upload_id", ondelete="SET NULL"
            ),
        ),
    )

    bind = op.get_bind()
    now = datetime.now(UTC)
    farming_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
        {"slug": "farming"},
    )
    if farming_id is None:
        last_order = bind.scalar(sa.text("SELECT COALESCE(MAX(sort_order), 0) FROM catalog_categories"))
        bind.execute(
            sa.text(
                "INSERT INTO catalog_categories "
                "(slug, name, sort_order, is_visible, created_at, updated_at) "
                "VALUES (:slug, :name, :sort_order, TRUE, :now, :now)"
            ),
            {"slug": "farming", "name": "种田", "sort_order": int(last_order) + 1, "now": now},
        )
        farming_id = bind.scalar(
            sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
            {"slug": "farming"},
        )
    casual_id = bind.scalar(
        sa.text("SELECT id FROM catalog_categories WHERE slug = :slug"),
        {"slug": "casual"},
    )
    if casual_id is not None:
        # 只迁移仍在默认休闲分类的朝花夕拾，保留管理员自行调整的归属。
        bind.execute(
            sa.text(
                "UPDATE catalog_projects SET category_id = :farming_id, updated_at = :now "
                "WHERE slug = :slug AND category_id = :casual_id"
            ),
            {"farming_id": farming_id, "now": now, "slug": "fablespace", "casual_id": casual_id},
        )

    # 已确认的作者只补空署名；管理员改过作者时不覆盖，也不误关联到他人主页。
    confirmed_authors = (
        ("voxel-tides", "Ericsmoon", "https://linux.do/u/ericsmoon"),
        ("yu-gi-oh-destiny-duel", "Frank_Cheung", "https://linux.do/u/frank_cheung/summary"),
        ("zhi-guai-lu", "feng98", "https://linux.do/u/feng98"),
        ("liuxin-watermelon", "feng98", "https://linux.do/u/feng98"),
        ("xing-lei-shou-wei", "feng98", "https://linux.do/u/feng98"),
        ("sanguo-zhengshi", "Yiyokiki", "https://linux.do/u/yiyokiki/summary"),
        ("secondhand-3c-store", "cfmxy123", "https://linux.do/u/cfmxy123"),
        ("sneaky-thief", "Shiyu", "https://linux.do/u/shiyu"),
        ("yeyu-tanglou", "qg_hs", "https://linux.do/u/qg_hs"),
        ("non-euclidean-lab", "Sworld", "https://linux.do/u/sworld/summary"),
        ("hyperbolic-room", "Sworld", "https://linux.do/u/sworld/summary"),
        ("geodesic-explorer", "Sworld", "https://linux.do/u/sworld/summary"),
        ("encounter-command-console", "yuzhi", "https://linux.do/u/yuzhi"),
        ("qin-imperial-factory", "easejun", "https://linux.do/u/easejun"),
        ("clock-out", "maomaowhy", "https://linux.do/u/maomaowhy/summary"),
    )
    for slug, author_name, author_url in confirmed_authors:
        bind.execute(
            sa.text(
                "UPDATE catalog_projects SET author_name = :author_name, updated_at = :now "
                "WHERE slug = :slug AND (author_name IS NULL OR author_name = '')"
            ),
            {"slug": slug, "author_name": author_name, "now": now},
        )
        bind.execute(
            sa.text(
                "UPDATE catalog_projects SET author_url = :author_url, updated_at = :now "
                "WHERE slug = :slug AND (author_url IS NULL OR author_url = '') "
                "AND BINARY author_name = BINARY :author_name"
            ),
            {"slug": slug, "author_name": author_name, "author_url": author_url, "now": now},
        )

    # CSGO 的来源清单使用复合署名；仅修正该导入值及旧主页路径，保留管理员的其他编辑。
    bind.execute(
        sa.text(
            "UPDATE catalog_projects SET author_name = :author_name, updated_at = :now "
            "WHERE slug = :slug AND (author_name IS NULL OR author_name = '' "
            "OR BINARY author_name = BINARY :imported_name)"
        ),
        {
            "slug": "csgo-desert",
            "author_name": "lin_ye",
            "imported_name": "lin_ye / lin ye",
            "now": now,
        },
    )
    bind.execute(
        sa.text(
            "UPDATE catalog_projects SET author_url = :author_url, updated_at = :now "
            "WHERE slug = :slug AND BINARY author_name = BINARY :author_name "
            "AND (author_url IS NULL OR author_url = '' "
            "OR BINARY author_url = BINARY :imported_url)"
        ),
        {
            "slug": "csgo-desert",
            "author_name": "lin_ye",
            "author_url": "https://linux.do/u/lin_ye/summary",
            "imported_url": "https://linux.do/u/lin_ye",
            "now": now,
        },
    )


def downgrade() -> None:
    """删除待审封面关联；先人工备份投稿封面，目录归属不自动回写。"""

    # 匿名封面上传保留 user_id=NULL；回退前须先清理或转移这些记录。
    anonymous_count = op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM uploads WHERE user_id IS NULL")
    )
    if anonymous_count:
        raise RuntimeError("0079 downgrade requires handling anonymous upload rows first")
    # 已审核的封面可能被正式项目复用，回退只删投稿关联，不删上传对象或分类。
    op.drop_constraint(
        "fk_catalog_submissions_cover_upload_id", "catalog_submissions", type_="foreignkey"
    )
    op.drop_column("catalog_submissions", "cover_upload_id")
    op.alter_column("uploads", "user_id", existing_type=sa.BigInteger(), nullable=False)
