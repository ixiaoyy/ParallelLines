"""add post revisions

Revision ID: 0012_post_revisions
Revises: 0011_spam_prevention
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_post_revisions"
down_revision: str | None = "0011_spam_prevention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "post_revisions",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column("post_id", sa.String(length=36), nullable=False, comment="被编辑帖子 ID。"),
        sa.Column(
            "topic_id",
            sa.String(length=36),
            nullable=False,
            comment="被编辑帖子所属主题 ID，用于历史查询和审计关联。",
        ),
        sa.Column(
            "editor_id",
            sa.String(length=36),
            nullable=True,
            comment="执行该次编辑或恢复操作的用户 ID；用户删除后为空。",
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            comment="同一帖子内递增的历史版本号，保存被覆盖前的内容版本。",
        ),
        sa.Column("raw_md", sa.Text(), nullable=False, comment="编辑前的原始 Markdown 内容。"),
        sa.Column(
            "cooked_html",
            sa.Text(),
            nullable=False,
            comment="编辑前已渲染/清洗的 HTML 内容。",
        ),
        sa.Column(
            "edit_reason",
            sa.String(length=500),
            nullable=True,
            comment="编辑人填写的原因；为空表示未填写。",
        ),
        sa.Column(
            "summary",
            sa.String(length=500),
            nullable=False,
            comment="系统生成或编辑人提供的版本摘要。",
        ),
        sa.Column(
            "restored_from_revision_id",
            sa.String(length=36),
            nullable=True,
            comment="若该版本由恢复操作产生，指向被恢复的历史版本 ID；否则为空。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="该历史版本保存时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["restored_from_revision_id"],
            ["post_revisions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "version_number", name="uq_post_revisions_post_version"),
        comment="帖子编辑历史版本，保存编辑前正文、编辑人、原因和恢复来源。",
    )
    op.create_index(
        "ix_post_revisions_post_created",
        "post_revisions",
        ["post_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_post_revisions_editor_created",
        "post_revisions",
        ["editor_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_post_revisions_editor_created", table_name="post_revisions")
    op.drop_index("ix_post_revisions_post_created", table_name="post_revisions")
    op.drop_table("post_revisions")
