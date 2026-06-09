"""rename frontier board to hot news

Revision ID: 0053_rename_frontier_to_hot_news
Revises: 0052_rename_comics_board
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0053_rename_frontier_to_hot_news"
down_revision: str | None = "0052_rename_comics_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUGS = ("frontier", "news")
OLD_BOARD_NAMES = ("前沿快讯", "前沿资讯")
NEW_BOARD_NAME = "热点资讯"
OLD_BOARD_DESCRIPTION = "自动汇集 AI、科技、研究论文与开源工具动态，经人工审核后发布。"
NEW_BOARD_DESCRIPTION = "自动汇集 AI 科技与社会热点，经人工审核后发布。"
OLD_TOPIC_TAG = "前沿资讯"
OLD_TOPIC_TAG_SLUG = "frontier-news"
HOT_NEWS_TAG = "热点资讯"
HOT_NEWS_TAG_SLUG = "hot-news"
AI_TECH_TAG = "AI 科技"
AI_TECH_TAG_SLUG = "ai-tech"
SOCIAL_HOT_TAG = "社会热点"
SOCIAL_HOT_TAG_SLUG = "social-hot"

boards = sa.table(
    "boards",
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)


def upgrade() -> None:
    """Rename the public news board and seed the new hot-news tag split.

    Key parameters: none. Return value: none. Side effect: updates board/tag
    rows when the tables exist, merging the legacy tag without dropping topic
    links.
    """

    bind = op.get_bind()
    current_time = now()
    if table_exists(bind, "boards"):
        bind.execute(
            boards.update()
            .where(boards.c.slug.in_(BOARD_SLUGS), boards.c.name.in_(OLD_BOARD_NAMES))
            .values(
                name=NEW_BOARD_NAME,
                description=NEW_BOARD_DESCRIPTION,
                updated_at=current_time,
            )
        )
    if not table_exists(bind, "tags"):
        return
    merge_or_ensure_tag(bind, OLD_TOPIC_TAG, HOT_NEWS_TAG, HOT_NEWS_TAG_SLUG, current_time)
    ensure_tag(bind, AI_TECH_TAG, AI_TECH_TAG_SLUG, current_time)
    ensure_tag(bind, SOCIAL_HOT_TAG, SOCIAL_HOT_TAG_SLUG, current_time)


def downgrade() -> None:
    """Restore the previous frontier board name while preserving category tags.

    Key parameters: none. Return value: none. Side effect: renames the board
    and folds `热点资讯` links back to `前沿资讯`; `AI 科技` / `社会热点`
    remain to avoid losing user-created tags.
    """

    bind = op.get_bind()
    current_time = now()
    if table_exists(bind, "boards"):
        bind.execute(
            boards.update()
            .where(boards.c.slug.in_(BOARD_SLUGS), boards.c.name == NEW_BOARD_NAME)
            .values(
                name="前沿资讯",
                description=OLD_BOARD_DESCRIPTION,
                updated_at=current_time,
            )
        )
    if table_exists(bind, "tags"):
        merge_or_ensure_tag(bind, HOT_NEWS_TAG, OLD_TOPIC_TAG, OLD_TOPIC_TAG_SLUG, current_time)


def merge_or_ensure_tag(
    bind: sa.Connection,
    old_name: str,
    new_name: str,
    new_slug: str,
    current_time: datetime,
) -> int:
    """Rename one tag, or merge it into an existing destination tag.

    Key parameters: `old_name` is the legacy label, `new_name`/`new_slug`
    define the destination. Return value: destination tag ID. Side effect:
    updates tag rows and moves join-table links when both tags already exist.
    """

    old_id = tag_id_by_name(bind, old_name)
    new_id = tag_id_by_name(bind, new_name)
    if old_id is None:
        return ensure_tag(bind, new_name, new_slug, current_time)
    if new_id is None:
        bind.execute(
            tags.update()
            .where(tags.c.id == old_id)
            .values(name=new_name, slug=new_slug, updated_at=current_time)
        )
        return int(old_id)
    if old_id != new_id:
        move_tag_links(bind, int(old_id), int(new_id))
        bind.execute(tags.delete().where(tags.c.id == old_id))
    return int(new_id)


def ensure_tag(bind: sa.Connection, name: str, slug: str, current_time: datetime) -> int:
    """Create a tag when missing and return the existing or new ID.

    Key parameters: `name` and `slug` are the desired public tag label and
    stable slug. Return value: tag ID. Side effect: may insert one tag row.
    """

    by_name = tag_id_by_name(bind, name)
    if by_name is not None:
        return int(by_name)
    by_slug = bind.execute(sa.select(tags.c.id).where(tags.c.slug == slug)).scalar()
    if by_slug is not None:
        return int(by_slug)
    bind.execute(
        tags.insert().values(
            name=name,
            slug=slug,
            topic_count=0,
            created_at=current_time,
            updated_at=current_time,
        )
    )
    inserted_id = tag_id_by_name(bind, name)
    if inserted_id is None:
        raise RuntimeError(f"tag_insert_failed:{name}")
    return int(inserted_id)


def move_tag_links(bind: sa.Connection, old_tag_id: int, new_tag_id: int) -> None:
    """Move topic-tag links from a legacy tag to the destination tag.

    Key parameters: `old_tag_id` and `new_tag_id` are tag primary keys.
    Return value: none. Side effect: inserts missing destination links and
    deletes old links.
    """

    if not table_exists(bind, "topic_tags"):
        return
    topic_ids = list(
        bind.execute(
            sa.select(topic_tags.c.topic_id).where(topic_tags.c.tag_id == old_tag_id)
        ).scalars()
    )
    for topic_id in topic_ids:
        exists = bind.execute(
            sa.select(topic_tags.c.topic_id).where(
                topic_tags.c.topic_id == topic_id,
                topic_tags.c.tag_id == new_tag_id,
            )
        ).first()
        if exists:
            continue
        bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=new_tag_id))
    bind.execute(topic_tags.delete().where(topic_tags.c.tag_id == old_tag_id))


def tag_id_by_name(bind: sa.Connection, name: str) -> int | None:
    """Look up a tag primary key by its unique display name.

    Key parameter: `name` is the tag label to find. Return value: tag ID or
    none. Side effect: reads the tags table.
    """

    value = bind.execute(sa.select(tags.c.id).where(tags.c.name == name)).scalar()
    return int(value) if value is not None else None


def now() -> datetime:
    """Return the current UTC timestamp for migration bookkeeping.

    Key parameters: none. Return value: timezone-aware UTC datetime. Side
    effect: none.
    """

    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check table existence before touching optional content tables.

    Key parameter: `table_name` is the SQL table to inspect. Return value:
    true when the table exists. Side effect: reads database metadata.
    """

    return sa.inspect(bind).has_table(table_name)
