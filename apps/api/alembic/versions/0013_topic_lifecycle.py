"""add topic lifecycle merge pointer

Revision ID: 0013_topic_lifecycle
Revises: 0012_post_revisions
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_topic_lifecycle"
down_revision: str | None = "0012_post_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("topics") as batch_op:
        batch_op.add_column(
            sa.Column(
                "merged_into_topic_id",
                sa.BigInteger(),
                nullable=True,
                comment="主题合并后的目标主题 ID；为空表示未合并。",
            )
        )
        batch_op.create_foreign_key(
            "fk_topics_merged_into_topic_id_topics",
            "topics",
            ["merged_into_topic_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("topics") as batch_op:
        batch_op.drop_constraint("fk_topics_merged_into_topic_id_topics", type_="foreignkey")
        batch_op.drop_column("merged_into_topic_id")
