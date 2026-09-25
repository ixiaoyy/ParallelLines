"""Add catalog submissions and optional project authors.

Revision ID: 0077_catalog_submissions
Revises: 0076_catalog_card_game
Create Date: 2026-09-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0077_catalog_submissions"
down_revision: str | None = "0076_catalog_card_game"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保存游客待审投稿；作者署名由管理员审核后写入正式项目。"""

    op.add_column("catalog_projects", sa.Column("author_name", sa.String(length=120)))
    op.add_column("catalog_projects", sa.Column("author_url", sa.String(length=2048)))
    op.create_table(
        "catalog_submissions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category_name", sa.String(length=120), nullable=False),
        sa.Column("project_name", sa.String(length=120), nullable=False),
        sa.Column("destination_url", sa.String(length=2048), nullable=False),
        sa.Column("author_name", sa.String(length=120)),
        sa.Column("contact", sa.String(length=200)),
        sa.Column("submitter_ip_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("pending_url_digest", sa.CHAR(length=64)),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("catalog_projects.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "reviewed_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_catalog_submissions_status",
        ),
        sa.UniqueConstraint("pending_url_digest", name="uq_catalog_submissions_pending_url_digest"),
    )
    op.create_index(
        "ix_catalog_submissions_status_created_id",
        "catalog_submissions",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_catalog_submissions_ip_created",
        "catalog_submissions",
        ["submitter_ip_digest", "created_at"],
    )


def downgrade() -> None:
    """删除投稿表和署名列；投稿、联系方式、作者名及署名链接会丢失。"""

    # 回退前须另行备份投稿和署名数据；正式目录项目仍会保留。
    op.drop_index("ix_catalog_submissions_ip_created", table_name="catalog_submissions")
    op.drop_index("ix_catalog_submissions_status_created_id", table_name="catalog_submissions")
    op.drop_table("catalog_submissions")
    op.drop_column("catalog_projects", "author_url")
    op.drop_column("catalog_projects", "author_name")
