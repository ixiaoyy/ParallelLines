"""add board management settings

Revision ID: 0022_board_management
Revises: 0021_user_social_pm
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_board_management"
down_revision: str | None = "0021_user_social_pm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("boards") as batch_op:
        batch_op.add_column(
            sa.Column(
                "parent_board_id",
                sa.BigInteger(),
                nullable=True,
                comment="父版块 ID；为空表示顶层版块。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "required_tags",
                sa.JSON(),
                nullable=True,
                comment="发帖必须包含的规范化标签名列表；为空或空数组表示不强制。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "allowed_tags",
                sa.JSON(),
                nullable=True,
                comment="允许使用的规范化标签名列表；为空或空数组表示不限制。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "post_template",
                sa.Text(),
                nullable=True,
                comment="该版块新主题默认 Markdown 模板；为空表示不预填。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_notification_level",
                sa.String(length=32),
                nullable=False,
                server_default="normal",
                comment="新关注者或受邀成员默认版块通知级别。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_sort",
                sa.String(length=32),
                nullable=False,
                server_default="latest",
                comment="版块主题默认排序：latest、hot 或 top。",
            )
        )
        batch_op.create_foreign_key(
            "fk_boards_parent_board_id_boards",
            "boards",
            ["parent_board_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_boards_parent", ["parent_board_id"])


def downgrade() -> None:
    with op.batch_alter_table("boards") as batch_op:
        batch_op.drop_index("ix_boards_parent")
        batch_op.drop_constraint("fk_boards_parent_board_id_boards", type_="foreignkey")
        batch_op.drop_column("default_sort")
        batch_op.drop_column("default_notification_level")
        batch_op.drop_column("post_template")
        batch_op.drop_column("allowed_tags")
        batch_op.drop_column("required_tags")
        batch_op.drop_column("parent_board_id")
