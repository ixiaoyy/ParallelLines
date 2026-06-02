"""add deduplicated topic views

Revision ID: 0049_topic_views
Revises: 0048_refine_memory_notes_template
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0049_topic_views"
down_revision: str | None = "0048_refine_memory_notes_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the per-topic viewer dedupe table for browser/user view counts."""

    op.create_table(
        "topic_views",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("topic_id", sa.BigInteger(), nullable=False, comment="被浏览主题 ID。"),
        sa.Column(
            "viewer_key",
            sa.String(length=96),
            nullable=False,
            comment="浏览者去重键；保存登录用户或匿名访客标识的哈希，不保存原始访客 ID。",
        ),
        sa.Column(
            "first_viewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="该浏览者首次计入主题浏览数的时间（UTC）。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间（UTC）。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录最后更新时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "viewer_key", name="uq_topic_views_topic_viewer"),
        comment="主题浏览去重记录，用于保证同一浏览者只增加一次浏览数。",
    )
    op.create_index("ix_topic_views_viewer_key", "topic_views", ["viewer_key"], unique=False)


def downgrade() -> None:
    """Drop the topic-view dedupe table and its secondary index."""

    op.drop_index("ix_topic_views_viewer_key", table_name="topic_views")
    op.drop_table("topic_views")
