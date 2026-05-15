"""create interactions and notifications

Revision ID: 0003_create_interactions_notifications
Revises: 0002_create_forum_core
Create Date: 2026-05-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_create_interactions_notifications"
down_revision: str | None = "0002_create_forum_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "target_type",
            "target_id",
            "user_id",
            "type",
            name="uq_reactions_target_user_type",
        ),
    )
    op.create_index("ix_reactions_target", "reactions", ["target_type", "target_id"])

    op.create_table(
        "bookmarks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("target_type", "target_id", "user_id", name="uq_bookmarks_target_user"),
    )
    op.create_index("ix_bookmarks_target", "bookmarks", ["target_type", "target_id"])
    op.create_index("ix_bookmarks_user_created", "bookmarks", ["user_id", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("topic_id", sa.String(length=36), nullable=True),
        sa.Column("post_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "read_at", "created_at"],
    )
    op.create_index("ix_notifications_topic_created", "notifications", ["topic_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_topic_created", table_name="notifications")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_bookmarks_user_created", table_name="bookmarks")
    op.drop_index("ix_bookmarks_target", table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_index("ix_reactions_target", table_name="reactions")
    op.drop_table("reactions")
