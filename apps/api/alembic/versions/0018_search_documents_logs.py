"""add search documents and logs

Revision ID: 0018_search_documents_logs
Revises: 0017_backup_artifacts
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_search_documents_logs"
down_revision: str | None = "0017_backup_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("topic_id", sa.BigInteger(), nullable=False, comment="关联主题 ID。"),
        sa.Column("board_id", sa.BigInteger(), nullable=False, comment="关联版块 ID。"),
        sa.Column("author_id", sa.BigInteger(), nullable=False, comment="主题作者用户 ID。"),
        sa.Column(
            "author_username",
            sa.String(length=64),
            nullable=False,
            comment="主题作者用户名快照。",
        ),
        sa.Column(
            "topic_status",
            sa.String(length=32),
            nullable=False,
            comment="主题状态快照：open、closed 或 archived。",
        ),
        sa.Column("title", sa.String(length=180), nullable=False, comment="搜索索引中的主题标题。"),
        sa.Column("body", sa.Text(), nullable=False, comment="可见帖子 Markdown 聚合正文。"),
        sa.Column(
            "tags_text",
            sa.Text(),
            nullable=False,
            comment="标签名称、标签 slug 和作者名聚合文本。",
        ),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="索引文档最后生成时间（UTC）。",
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
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="全文搜索索引文档，保存主题可搜索文本与过滤快照。",
    )
    op.create_index("ix_search_documents_topic", "search_documents", ["topic_id"], unique=True)
    op.create_index(
        "ix_search_documents_board_updated",
        "search_documents",
        ["board_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_search_documents_author_updated",
        "search_documents",
        ["author_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_search_documents_status_updated",
        "search_documents",
        ["topic_status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "search_logs",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=True,
            comment="搜索用户 ID；匿名搜索为空。",
        ),
        sa.Column(
            "query",
            sa.String(length=120),
            nullable=False,
            comment="用户原始搜索词截断快照。",
        ),
        sa.Column(
            "normalized_query",
            sa.String(length=120),
            nullable=False,
            comment="归一化搜索词，用于热词和无结果分析。",
        ),
        sa.Column("filters", sa.JSON(), nullable=False, comment="搜索过滤条件 JSON 快照。"),
        sa.Column("result_count", sa.Integer(), nullable=False, comment="本次搜索返回结果数量。"),
        sa.Column("has_results", sa.Boolean(), nullable=False, comment="本次搜索是否有结果。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="搜索查询日志，用于无结果分析、热词统计和运营分析。",
    )
    op.create_index(
        "ix_search_logs_query_created",
        "search_logs",
        ["normalized_query", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_search_logs_user_created",
        "search_logs",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_search_logs_has_results_created",
        "search_logs",
        ["has_results", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_search_logs_has_results_created", table_name="search_logs")
    op.drop_index("ix_search_logs_user_created", table_name="search_logs")
    op.drop_index("ix_search_logs_query_created", table_name="search_logs")
    op.drop_table("search_logs")
    op.drop_index("ix_search_documents_status_updated", table_name="search_documents")
    op.drop_index("ix_search_documents_author_updated", table_name="search_documents")
    op.drop_index("ix_search_documents_board_updated", table_name="search_documents")
    op.drop_index("ix_search_documents_topic", table_name="search_documents")
    op.drop_table("search_documents")
