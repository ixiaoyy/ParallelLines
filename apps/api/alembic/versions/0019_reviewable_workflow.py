"""add reviewable workflow

Revision ID: 0019_reviewable_workflow
Revises: 0018_search_documents_logs
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_reviewable_workflow"
down_revision: str | None = "0018_search_documents_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviewables",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "type",
            sa.String(length=32),
            nullable=False,
            comment=(
                "审核对象类型：flag、queued_topic、queued_post、queued_edit、appeal "
                "或 system。"
            ),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment=(
                "审核状态：pending、claimed、approved、rejected、hidden、deleted、silenced、"
                "escalated 或 appealed。"
            ),
        ),
        sa.Column("priority", sa.Integer(), nullable=False, comment="审核优先级，数值越小越靠前。"),
        sa.Column("source", sa.String(length=64), nullable=False, comment="审核来源。"),
        sa.Column(
            "source_summary",
            sa.String(length=500),
            nullable=False,
            comment="可展示的来源摘要，不包含敏感规则明文。",
        ),
        sa.Column("target_type", sa.String(length=32), nullable=True, comment="审核目标类型。"),
        sa.Column("target_id", sa.BigInteger(), nullable=True, comment="审核目标 ID。"),
        sa.Column("board_id", sa.BigInteger(), nullable=True, comment="相关版块 ID。"),
        sa.Column("topic_id", sa.BigInteger(), nullable=True, comment="相关主题 ID。"),
        sa.Column("post_id", sa.BigInteger(), nullable=True, comment="相关帖子 ID。"),
        sa.Column("flag_id", sa.BigInteger(), nullable=True, comment="关联举报 ID。"),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="创建审核项的用户 ID；系统创建时为空。",
        ),
        sa.Column(
            "target_user_id",
            sa.BigInteger(),
            nullable=True,
            comment="被审核或受处理影响的用户 ID。",
        ),
        sa.Column(
            "assigned_to_id",
            sa.BigInteger(),
            nullable=True,
            comment="当前认领审核员 ID；未认领为空。",
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="审核项被认领时间；未认领为空。",
        ),
        sa.Column(
            "resolved_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="最终处理审核员 ID；未处理为空。",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最终处理时间；未处理为空。",
        ),
        sa.Column(
            "data",
            sa.JSON(),
            nullable=False,
            comment="审核上下文 JSON，普通用户接口不得返回敏感字段。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录创建时间。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="记录更新时间。",
        ),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flag_id"], ["flags.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="统一审核对象，承载举报、待审内容、自动规则和申诉处理状态。",
    )
    op.create_index(
        "ix_reviewables_status_created", "reviewables", ["status", "created_at"]
    )
    op.create_index(
        "ix_reviewables_board_status", "reviewables", ["board_id", "status"]
    )
    op.create_index(
        "ix_reviewables_assignee_status", "reviewables", ["assigned_to_id", "status"]
    )
    op.create_index(
        "ix_reviewables_created_by_status", "reviewables", ["created_by_id", "status"]
    )
    op.create_index("ix_reviewables_flag", "reviewables", ["flag_id"])

    op.create_table(
        "reviewable_events",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "reviewable_id",
            sa.BigInteger(),
            nullable=False,
            comment="关联审核对象 ID。",
        ),
        sa.Column("actor_id", sa.BigInteger(), nullable=True, comment="触发事件的用户 ID。"),
        sa.Column(
            "event",
            sa.String(length=32),
            nullable=False,
            comment="事件类型：created、claimed、released、decided 或 appealed。",
        ),
        sa.Column("from_status", sa.String(length=32), nullable=True, comment="事件前审核状态。"),
        sa.Column("to_status", sa.String(length=32), nullable=True, comment="事件后审核状态。"),
        sa.Column("note", sa.Text(), nullable=True, comment="审核员备注或申诉理由。"),
        sa.Column("data", sa.JSON(), nullable=False, comment="事件上下文 JSON，不包含密码或令牌。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="事件发生时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewable_id"], ["reviewables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="审核对象事件流水，记录认领、释放、处理和申诉。",
    )
    op.create_index(
        "ix_reviewable_events_reviewable_created",
        "reviewable_events",
        ["reviewable_id", "created_at"],
    )
    op.create_index(
        "ix_reviewable_events_actor_created",
        "reviewable_events",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_reviewable_events_event_created",
        "reviewable_events",
        ["event", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reviewable_events_event_created", table_name="reviewable_events")
    op.drop_index("ix_reviewable_events_actor_created", table_name="reviewable_events")
    op.drop_index("ix_reviewable_events_reviewable_created", table_name="reviewable_events")
    op.drop_table("reviewable_events")
    op.drop_index("ix_reviewables_flag", table_name="reviewables")
    op.drop_index("ix_reviewables_created_by_status", table_name="reviewables")
    op.drop_index("ix_reviewables_assignee_status", table_name="reviewables")
    op.drop_index("ix_reviewables_board_status", table_name="reviewables")
    op.drop_index("ix_reviewables_status_created", table_name="reviewables")
    op.drop_table("reviewables")
