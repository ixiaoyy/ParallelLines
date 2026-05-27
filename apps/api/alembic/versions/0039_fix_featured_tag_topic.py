"""fix featured tag topic

Revision ID: 0039_fix_featured_tag_topic
Revises: 0038_refine_public_tag_taxonomy
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0039_fix_featured_tag_topic"
down_revision: str | None = "0038_refine_public_tag_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
topics = sa.table(
    "topics",
    sa.column("id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)
topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "tags") or not table_exists(bind, "topics"):
        return

    featured_tag_id = ensure_tag(bind, "精华神帖", "featured")
    old_featured = bind.execute(sa.select(tags.c.id).where(tags.c.name == "精华")).first()
    if old_featured and int(old_featured.id) != featured_tag_id:
        merge_tag_rows(bind, int(old_featured.id), featured_tag_id)

    topic_ids = bind.execute(
        sa.select(topics.c.id).where(
            topics.c.deleted_at.is_(None),
            sa.or_(
                topics.c.slug == "forum-intent",
                topics.c.title == "论坛初衷：记录、连接与共同成长",
            ),
        )
    ).scalars()
    for topic_id in topic_ids:
        exists = bind.execute(
            sa.select(topic_tags.c.topic_id)
            .where(topic_tags.c.topic_id == topic_id, topic_tags.c.tag_id == featured_tag_id)
            .limit(1)
        ).first()
        if not exists:
            bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=featured_tag_id))

    recompute_tag_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def ensure_tag(bind: sa.Connection, name: str, slug: str) -> int:
    row = bind.execute(
        sa.select(tags.c.id).where(sa.or_(tags.c.name == name, tags.c.slug == slug)).limit(1)
    ).first()
    if row:
        bind.execute(
            tags.update()
            .where(tags.c.id == row.id)
            .values(name=name, slug=slug, updated_at=now())
        )
        return int(row.id)
    bind.execute(
        tags.insert().values(
            name=name,
            slug=slug,
            topic_count=0,
            created_at=now(),
            updated_at=now(),
        )
    )
    return int(bind.execute(sa.select(tags.c.id).where(tags.c.slug == slug)).scalar_one())


def merge_tag_rows(bind: sa.Connection, source_tag_id: int, target_tag_id: int) -> None:
    topic_ids = bind.execute(
        sa.select(topic_tags.c.topic_id).where(topic_tags.c.tag_id == source_tag_id)
    ).scalars()
    for topic_id in topic_ids:
        exists = bind.execute(
            sa.select(topic_tags.c.topic_id)
            .where(topic_tags.c.topic_id == topic_id, topic_tags.c.tag_id == target_tag_id)
            .limit(1)
        ).first()
        if not exists:
            bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=target_tag_id))
    bind.execute(topic_tags.delete().where(topic_tags.c.tag_id == source_tag_id))
    bind.execute(tags.delete().where(tags.c.id == source_tag_id))


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
