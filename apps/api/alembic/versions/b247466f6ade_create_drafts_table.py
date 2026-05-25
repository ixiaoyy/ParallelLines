"""create drafts table

Revision ID: b247466f6ade
Revises: 0019_reviewable_workflow
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b247466f6ade"
down_revision: str | None = "0019_reviewable_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="草稿所属用户 ID。"),
        sa.Column(
            "target_type",
            sa.String(length=32),
            nullable=False,
            comment="草稿目标类型：new_topic 表示新主题，topic 表示某主题回复。",
        ),
        sa.Column(
            "target_id",
            sa.String(length=64),
            nullable=False,
            comment="草稿目标 ID；新主题草稿为空字符串，回复草稿为数值主题 ID 字符串。",
        ),
        sa.Column(
            "draft_type",
            sa.String(length=32),
            nullable=False,
            comment="草稿内容类型：topic 表示主题草稿，reply 表示回复草稿。",
        ),
        sa.Column(
            "data",
            sa.JSON(),
            nullable=False,
            comment="草稿结构化数据，保存标题、正文、标签等客户端状态。",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            comment="草稿版本号，用于客户端-服务端冲突检测。",
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_drafts_user_target"),
        comment="用户未发布的帖子与主题草稿，支持多设备恢复与冲突处理。",
    )
    op.create_index("ix_drafts_user_id", "drafts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_drafts_user_id", table_name="drafts")
    op.drop_table("drafts")
