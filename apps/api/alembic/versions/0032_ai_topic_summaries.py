"""add ai topic summaries

Revision ID: 0032_ai_topic_summaries
Revises: 0031_external_integrations
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_ai_topic_summaries"
down_revision: str | None = "0031_external_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_topic_summaries",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
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
        sa.Column(
            "topic_id",
            sa.BigInteger(),
            nullable=False,
            comment="被总结的主题 ID，每个主题最多一条当前摘要。",
        ),
        sa.Column(
            "summary", sa.Text(), nullable=False, comment="AI 生成或本地确定性生成的主题摘要。"
        ),
        sa.Column("key_points", sa.JSON(), nullable=False, comment="关键结论或行动项数组。"),
        sa.Column(
            "key_post_ids", sa.JSON(), nullable=False, comment="贡献摘要的关键帖子 ID 数组。"
        ),
        sa.Column(
            "model_name",
            sa.String(length=80),
            nullable=False,
            server_default="local-deterministic",
            comment="生成摘要的模型或本地算法名称。",
        ),
        sa.Column(
            "cost_units",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="本次摘要估算成本单位，用于成本控制展示。",
        ),
        sa.Column(
            "refreshed_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="触发刷新摘要的用户 ID；用户删除后为空。",
        ),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False, comment="摘要生成时间。"
        ),
        sa.ForeignKeyConstraint(["refreshed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", name="uq_ai_topic_summaries_topic"),
        comment="AI 主题摘要缓存，保存人工可刷新摘要、关键点、成本和生成元数据。",
    )
    op.create_index("ix_ai_topic_summaries_generated", "ai_topic_summaries", ["generated_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_topic_summaries_generated", table_name="ai_topic_summaries")
    op.drop_table("ai_topic_summaries")
