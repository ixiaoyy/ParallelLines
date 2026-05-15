"""create moderation flags and audit logs

Revision ID: 0004_create_moderation
Revises: 0003_create_interactions_notifications
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_create_moderation"
down_revision: str | None = "0003_create_interactions_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("reporter_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_flags_board_status", "flags", ["board_id", "status"])
    op.create_index("ix_flags_status_created", "flags", ["status", "created_at"])
    op.create_index("ix_flags_target", "flags", ["target_type", "target_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_board_created", "audit_logs", ["board_id", "created_at"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_board_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_flags_target", table_name="flags")
    op.drop_index("ix_flags_status_created", table_name="flags")
    op.drop_index("ix_flags_board_status", table_name="flags")
    op.drop_table("flags")
