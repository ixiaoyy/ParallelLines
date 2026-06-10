"""retire low-quality Caiwen frontier sources

Revision ID: 0054_retire_caiwen_frontier_sources
Revises: 0053_rename_frontier_to_hot_news
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0054_retire_caiwen_frontier_sources"
down_revision: str | None = "0053_rename_frontier_to_hot_news"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETIRED_SOURCE_KEYS = ("caiwen_ai_tech", "caiwen_social_hot")
OPEN_REVIEWABLE_STATUSES = ("pending", "claimed", "appealed")

frontier_news_sources = sa.table(
    "frontier_news_sources",
    sa.column("id", sa.BigInteger()),
    sa.column("key", sa.String()),
)

frontier_news_items = sa.table(
    "frontier_news_items",
    sa.column("id", sa.BigInteger()),
    sa.column("source_id", sa.BigInteger()),
    sa.column("reviewable_id", sa.BigInteger()),
)

reviewables = sa.table(
    "reviewables",
    sa.column("id", sa.BigInteger()),
    sa.column("status", sa.String()),
    sa.column("source", sa.String()),
)

reviewable_events = sa.table(
    "reviewable_events",
    sa.column("reviewable_id", sa.BigInteger()),
)


def upgrade() -> None:
    """Remove retired Caiwen sources and their still-open moderation queue rows.

    Key parameters: none. Return value: none. Side effect: deletes pending,
    claimed, or appealed reviewables linked to Caiwen frontier items, then
    deletes the retired source rows so future collection cannot enqueue them.
    """

    bind = op.get_bind()
    if not table_exists(bind, "frontier_news_sources"):
        return
    source_ids = list(
        bind.execute(
            sa.select(frontier_news_sources.c.id).where(
                frontier_news_sources.c.key.in_(RETIRED_SOURCE_KEYS)
            )
        ).scalars()
    )
    if not source_ids:
        return
    delete_open_reviewables_for_sources(bind, source_ids)
    bind.execute(
        frontier_news_sources.delete().where(frontier_news_sources.c.id.in_(source_ids))
    )


def downgrade() -> None:
    """Keep retired Caiwen sources removed when downgrading this cleanup.

    Key parameters: none. Return value: none. Side effect: none. The source
    retirement is intentionally irreversible to avoid reintroducing low-quality
    collection rows during operational rollback.
    """


def delete_open_reviewables_for_sources(bind: sa.Connection, source_ids: list[int]) -> None:
    """Delete queue-only reviewables linked to frontier items from retired sources.

    Key parameters: `bind` is the migration connection and `source_ids` are the
    retired source primary keys. Return value: none. Side effect: removes
    reviewable event rows and open reviewables before source deletion cascades
    the material rows.
    """

    if not table_exists(bind, "frontier_news_items") or not table_exists(bind, "reviewables"):
        return
    reviewable_ids = list(
        bind.execute(
            sa.select(frontier_news_items.c.reviewable_id).where(
                frontier_news_items.c.source_id.in_(source_ids),
                frontier_news_items.c.reviewable_id.is_not(None),
            )
        ).scalars()
    )
    if not reviewable_ids:
        return
    open_reviewable_ids = list(
        bind.execute(
            sa.select(reviewables.c.id).where(
                reviewables.c.id.in_(reviewable_ids),
                reviewables.c.source == "frontier_news",
                reviewables.c.status.in_(OPEN_REVIEWABLE_STATUSES),
            )
        ).scalars()
    )
    if not open_reviewable_ids:
        return
    if table_exists(bind, "reviewable_events"):
        bind.execute(
            reviewable_events.delete().where(
                reviewable_events.c.reviewable_id.in_(open_reviewable_ids)
            )
        )
    bind.execute(reviewables.delete().where(reviewables.c.id.in_(open_reviewable_ids)))


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether an optional table is present before cleanup queries run.

    Key parameter: `table_name` is the table to inspect. Return value: true
    when Alembic can safely query the table. Side effect: reads database
    metadata through SQLAlchemy inspection.
    """

    return sa.inspect(bind).has_table(table_name)
