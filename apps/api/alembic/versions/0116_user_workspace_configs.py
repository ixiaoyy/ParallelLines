"""新增账号独占的工作台云配置；不回填或改动既有表。

Revision ID: 0116_user_workspace_configs
Revises: 0115_add_three_browser_games
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0116_user_workspace_configs"
down_revision: str | None = "0115_add_three_browser_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建空表，使用与 users.id 一致的有符号 BIGINT。"""
    op.create_table(
        "user_workspace_configs",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("config_json", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_workspace_configs_user", ondelete="CASCADE"
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_user_workspace_configs_schema"),
        sa.CheckConstraint("revision >= 1", name="ck_user_workspace_configs_revision"),
        sa.CheckConstraint(
            "UPPER(JSON_TYPE(config_json)) = 'OBJECT'",
            name="ck_user_workspace_configs_object",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    """删除本表及用户云配置；已有数据时应先备份并单独批准降级。"""
    op.drop_table("user_workspace_configs")
