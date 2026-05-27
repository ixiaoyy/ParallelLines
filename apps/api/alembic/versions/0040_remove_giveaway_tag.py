"""remove giveaway tag

Revision ID: 0040_remove_giveaway_tag
Revises: 0039_fix_featured_tag_topic
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0040_remove_giveaway_tag"
down_revision: str | None = "0039_fix_featured_tag_topic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)
topics = sa.table(
    "topics",
    sa.column("id", sa.BigInteger()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "tags"):
        return

    giveaway_ids = list(
        bind.execute(
            sa.select(tags.c.id).where(sa.or_(tags.c.name == "抽奖", tags.c.slug == "giveaway"))
        ).scalars()
    )
    if not giveaway_ids:
        return

    bind.execute(topic_tags.delete().where(topic_tags.c.tag_id.in_(giveaway_ids)))
    bind.execute(tags.delete().where(tags.c.id.in_(giveaway_ids)))
    recompute_tag_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def recompute_tag_counters(bind: sa.Connection) -> None:
    for tag_id in bind.execute(sa.select(tags.c.id)).scalars().all():
        topic_count = bind.execute(
            sa.select(sa.func.count(sa.distinct(topic_tags.c.topic_id)))
            .select_from(topic_tags.join(topics, topic_tags.c.topic_id == topics.c.id))
            .where(topic_tags.c.tag_id == tag_id, topics.c.deleted_at.is_(None))
        ).scalar_one()
        bind.execute(
            tags.update()
            .where(tags.c.id == tag_id)
            .values(topic_count=topic_count, updated_at=now())
        )
