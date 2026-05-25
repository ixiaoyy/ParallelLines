"""add board invitations

Revision ID: 0008_board_invitations
Revises: 0007_add_user_level
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_board_invitations"
down_revision: str | None = "0007_add_user_level"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "board_invitations",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "board_id",
            sa.BigInteger(),
            nullable=False,
            comment="被邀请加入的版块 ID。",
        ),
        sa.Column(
            "inviter_id",
            sa.BigInteger(),
            nullable=False,
            comment="发出邀请的用户 ID。",
        ),
        sa.Column(
            "invitee_id",
            sa.BigInteger(),
            nullable=False,
            comment="被邀请的用户 ID。",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
            comment="邀请状态：pending、accepted、declined、revoked 或 expired。",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="邀请过期时间；为空表示当前首版不自动过期。",
        ),
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="邀请被接受、拒绝或撤回的时间。",
        ),
        sa.Column(
            "revoked_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="撤回邀请的用户 ID；为空表示未撤回。",
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
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="邀请制版块的成员邀请生命周期记录。",
    )
    op.create_index(
        "ix_board_invitations_invitee_status",
        "board_invitations",
        ["invitee_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_board_invitations_board_status",
        "board_invitations",
        ["board_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_board_invitations_board_status", table_name="board_invitations")
    op.drop_index("ix_board_invitations_invitee_status", table_name="board_invitations")
    op.drop_table("board_invitations")
