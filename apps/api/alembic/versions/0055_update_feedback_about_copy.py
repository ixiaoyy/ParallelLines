"""update community feedback about-topic copy

Revision ID: 0055_update_feedback_about_copy
Revises: 0054_retire_caiwen_frontier_sources
Create Date: 2026-06-10
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0055_update_feedback_about_copy"
down_revision: str | None = "0054_retire_caiwen_frontier_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEEDBACK_BOARD_SLUG = "feedback"
FEEDBACK_ABOUT_SLUG = "about-feedback"
FEEDBACK_TITLE = "关于「社区反馈」"
FEEDBACK_DESCRIPTION = "收集网站功能、社区体验和内容运营相关的建议、意见与问题反馈。"
FEEDBACK_PURPOSE = (
    "收集大家对产品功能、使用体验、内容组织和社区规则的建议、意见与问题反馈，方便持续改进。"
)
FEEDBACK_GUIDANCE = "功能建议、体验意见、问题反馈或社区规则/内容组织相关想法，都可以发在这里。"
FEEDBACK_PROBLEM_GUIDANCE = (
    "问题反馈请尽量补充复现步骤、截图、相关链接、发生时间和你看到的错误信息。"
)
FEEDBACK_ROUTE_GUIDANCE = "如果内容更适合其他板块，也可以在发布前重新选择。"
FEEDBACK_CLOSING = "希望这里能成为一个清楚、有用、友善的交流空间。"

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("description", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

topics = sa.table(
    "topics",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("pinned", sa.Boolean()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

posts = sa.table(
    "posts",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("post_number", sa.Integer()),
    sa.column("raw_md", sa.Text()),
    sa.column("cooked_html", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

search_documents = sa.table(
    "search_documents",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("body", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Update the existing community-feedback about topic and searchable copy.

    Key parameters: none. Return value: none. Side effect: updates the feedback
    board description, its pinned about topic first post, and the matching
    search document when those rows exist.
    """

    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "topics"):
        return
    board = bind.execute(
        sa.select(boards.c.id).where(boards.c.slug == FEEDBACK_BOARD_SLUG).limit(1)
    ).first()
    if board is None:
        return
    current_time = now()
    bind.execute(
        boards.update()
        .where(boards.c.id == board.id)
        .values(description=FEEDBACK_DESCRIPTION, updated_at=current_time)
    )
    topic = find_feedback_about_topic(bind, int(board.id))
    if topic is None:
        return
    bind.execute(
        topics.update()
        .where(topics.c.id == topic.id)
        .values(
            title=FEEDBACK_TITLE,
            slug=FEEDBACK_ABOUT_SLUG,
            pinned=True,
            updated_at=current_time,
        )
    )
    update_first_post(bind, int(topic.id), current_time)
    update_search_document(bind, int(topic.id), current_time)


def downgrade() -> None:
    """Leave the improved feedback copy in place on downgrade.

    Key parameters: none. Return value: none. Side effect: none. The newer
    wording is intentionally retained because it more accurately describes the
    feedback board's purpose.
    """


def find_feedback_about_topic(bind: sa.Connection, board_id: int):
    """Find the pinned feedback explanation topic by stable slug or title.

    Key parameters: `bind` is the migration connection and `board_id` is the
    feedback board ID. Return value: a topic row or none. Side effect: reads
    the `topics` table.
    """

    return bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board_id,
            sa.or_(topics.c.slug == FEEDBACK_ABOUT_SLUG, topics.c.title == FEEDBACK_TITLE),
        )
        .order_by(topics.c.id)
        .limit(1)
    ).first()


def update_first_post(bind: sa.Connection, topic_id: int, current_time: datetime) -> None:
    """Replace the first post body for the feedback about topic.

    Key parameters: `topic_id` identifies the topic and `current_time` is used
    for update bookkeeping. Return value: none. Side effect: updates the first
    post when it exists.
    """

    if not table_exists(bind, "posts"):
        return
    bind.execute(
        posts.update()
        .where(posts.c.topic_id == topic_id, posts.c.post_number == 1)
        .values(raw_md=feedback_markdown(), cooked_html=feedback_html(), updated_at=current_time)
    )


def update_search_document(bind: sa.Connection, topic_id: int, current_time: datetime) -> None:
    """Refresh search text for the updated feedback about topic.

    Key parameters: `topic_id` identifies the updated topic and `current_time`
    is used for update bookkeeping. Return value: none. Side effect: updates
    an existing `search_documents` row when present.
    """

    if not table_exists(bind, "search_documents"):
        return
    bind.execute(
        search_documents.update()
        .where(search_documents.c.topic_id == topic_id)
        .values(title=FEEDBACK_TITLE, body=feedback_markdown(), updated_at=current_time)
    )


def feedback_markdown() -> str:
    """Render the feedback about-topic Markdown used in posts and search.

    Key parameters: none. Return value: Markdown string. Side effect: none.
    """

    return (
        f"# {FEEDBACK_TITLE}\n\n"
        f"{FEEDBACK_DESCRIPTION}\n\n"
        f"这个板块用于{FEEDBACK_PURPOSE}\n\n"
        "## 适合发布\n\n"
        f"- {FEEDBACK_GUIDANCE}\n"
        f"- {FEEDBACK_PROBLEM_GUIDANCE}\n"
        f"- {FEEDBACK_ROUTE_GUIDANCE}\n\n"
        f"{FEEDBACK_CLOSING}"
    )


def feedback_html() -> str:
    """Render simple safe HTML matching the updated feedback Markdown.

    Key parameters: none. Return value: HTML string. Side effect: none.
    """

    return "".join(
        [
            f"<h1>{html.escape(FEEDBACK_TITLE)}</h1>",
            f"<p>{html.escape(FEEDBACK_DESCRIPTION)}</p>",
            f"<p>这个板块用于{html.escape(FEEDBACK_PURPOSE)}</p>",
            "<h2>适合发布</h2>",
            "<ul>",
            f"<li>{html.escape(FEEDBACK_GUIDANCE)}</li>",
            f"<li>{html.escape(FEEDBACK_PROBLEM_GUIDANCE)}</li>",
            f"<li>{html.escape(FEEDBACK_ROUTE_GUIDANCE)}</li>",
            "</ul>",
            f"<p>{html.escape(FEEDBACK_CLOSING)}</p>",
        ]
    )


def now() -> datetime:
    """Return the current UTC timestamp for migration bookkeeping.

    Key parameters: none. Return value: timezone-aware UTC datetime. Side
    effect: none.
    """

    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether an optional table exists before running data updates.

    Key parameter: `table_name` is the table to inspect. Return value: true
    when SQLAlchemy can safely query the table. Side effect: reads database
    metadata.
    """

    return sa.inspect(bind).has_table(table_name)
