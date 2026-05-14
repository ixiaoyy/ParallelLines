"""create forum core

Revision ID: 0002_create_forum_core
Revises: 0001_create_users
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_create_forum_core"
down_revision: str | None = "0001_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("topic_count", sa.Integer(), nullable=False),
        sa.Column("post_count", sa.Integer(), nullable=False),
        sa.Column("follower_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_boards_slug"),
    )
    op.create_index("ix_boards_slug", "boards", ["slug"])

    op.create_table(
        "board_members",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("notification_level", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("board_id", "user_id", name="uq_board_members_board_user"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("topic_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_tags_name"),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"])

    op.create_table(
        "topics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("reply_count", sa.Integer(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False),
        sa.Column("hot_score", sa.Float(), nullable=False),
        sa.Column("last_posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("board_id", "slug", name="uq_topics_board_slug"),
    )
    op.create_index("ix_topics_board_hot_score", "topics", ["board_id", "hot_score"])
    op.create_index("ix_topics_board_last_posted", "topics", ["board_id", "last_posted_at"])

    op.create_table(
        "topic_tags",
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("topic_id", "tag_id"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("post_number", sa.Integer(), nullable=False),
        sa.Column("raw_md", sa.Text(), nullable=False),
        sa.Column("cooked_html", sa.Text(), nullable=False),
        sa.Column("reply_count", sa.Integer(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("topic_id", "post_number", name="uq_posts_topic_number"),
    )

    op.create_table(
        "topic_reads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("last_read_post_number", sa.Integer(), nullable=False),
        sa.Column("notification_level", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_topic_reads_user_topic"),
    )


def downgrade() -> None:
    op.drop_table("topic_reads")
    op.drop_table("posts")
    op.drop_table("topic_tags")
    op.drop_index("ix_topics_board_last_posted", table_name="topics")
    op.drop_index("ix_topics_board_hot_score", table_name="topics")
    op.drop_table("topics")
    op.drop_index("ix_tags_slug", table_name="tags")
    op.drop_table("tags")
    op.drop_table("board_members")
    op.drop_index("ix_boards_slug", table_name="boards")
    op.drop_table("boards")
