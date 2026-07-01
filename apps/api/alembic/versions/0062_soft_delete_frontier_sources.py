"""soft delete frontier sources

Revision ID: 0062_soft_delete_frontier_sources
Revises: 0061_add_site_visits
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0062_soft_delete_frontier_sources"
down_revision: str | None = "0061_add_site_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add administrator-controlled soft deletion for frontier sources.

    Key parameters: none. Return value: none. Side effect: adds `deleted_at`
    and an index used by admin listing and scheduled source collection.
    """

    op.add_column(
        "frontier_news_sources",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="管理员删除该来源的时间；为空表示仍在后台可见并可被采集。",
        ),
    )
    op.create_index(
        "ix_frontier_news_sources_deleted_enabled",
        "frontier_news_sources",
        ["deleted_at", "enabled", "last_checked_at"],
    )


def downgrade() -> None:
    """Remove frontier source soft-delete storage on schema downgrade.

    Key parameters: none. Return value: none. Side effect: drops the index and
    `deleted_at` column added by this revision.
    """

    op.drop_index("ix_frontier_news_sources_deleted_enabled", table_name="frontier_news_sources")
    op.drop_column("frontier_news_sources", "deleted_at")
