"""add public topic feed sort indexes

Revision ID: 0056_topic_feed_sort_indexes
Revises: 0055_update_feedback_about_copy
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0056_topic_feed_sort_indexes"
down_revision: str | None = "0055_update_feedback_about_copy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create composite indexes for public topic feed sorting.

    Key parameters: none. Return value: none. Side effect: creates MySQL
    indexes that match public latest, hot, top, and votes feed filters.
    """

    op.create_index(
        "ix_topics_public_latest_feed",
        "topics",
        ["visibility", "deleted_at", "pinned", "last_posted_at", "id"],
    )
    op.create_index(
        "ix_topics_public_hot_feed",
        "topics",
        ["visibility", "deleted_at", "hot_score", "last_posted_at", "id"],
    )
    op.create_index(
        "ix_topics_public_top_feed",
        "topics",
        ["visibility", "deleted_at", "like_count", "reply_count", "id"],
    )
    op.create_index(
        "ix_topics_public_votes_feed",
        "topics",
        ["visibility", "deleted_at", "vote_score", "vote_count", "last_posted_at", "id"],
    )


def downgrade() -> None:
    """Drop composite public topic feed indexes.

    Key parameters: none. Return value: none. Side effect: removes only indexes
    created by this revision.
    """

    op.drop_index("ix_topics_public_votes_feed", table_name="topics")
    op.drop_index("ix_topics_public_top_feed", table_name="topics")
    op.drop_index("ix_topics_public_hot_feed", table_name="topics")
    op.drop_index("ix_topics_public_latest_feed", table_name="topics")
