"""add user points experience

Revision ID: 0024_user_points_experience
Revises: 0023_topic_solved_voting
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_user_points_experience"
down_revision: str | None = "0023_topic_solved_voting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "points_balance",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="用户当前积分余额，可由行为奖励或管理员调整。默认 0。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "experience_total",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="用户累计经验值，用于按集中等级规则计算 level。默认 0。",
            )
        )

    users = sa.table(
        "users",
        sa.column("level", sa.Integer()),
        sa.column("experience_total", sa.Integer()),
    )
    op.execute(
        users.update().values(
            experience_total=sa.case(
                (users.c.level >= 10, 6000),
                (users.c.level == 9, 4600),
                (users.c.level == 8, 3400),
                (users.c.level == 7, 2400),
                (users.c.level == 6, 1600),
                (users.c.level == 5, 1000),
                (users.c.level == 4, 600),
                (users.c.level == 3, 300),
                (users.c.level == 2, 150),
                (users.c.level == 1, 50),
                else_=0,
            )
        )
    )

    op.create_table(
        "user_point_events",
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
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="获得变更的用户 ID。"),
        sa.Column(
            "source_type",
            sa.String(length=48),
            nullable=False,
            comment="积分/经验来源类型，如 topic_created、content_liked 或 admin_adjustment。",
        ),
        sa.Column(
            "source_id",
            sa.String(length=96),
            nullable=True,
            comment="来源对象 ID；人工调整或系统事件可为空。",
        ),
        sa.Column("points_delta", sa.Integer(), nullable=False, comment="本次积分变化量。"),
        sa.Column("experience_delta", sa.Integer(), nullable=False, comment="本次经验变化量。"),
        sa.Column("balance_after", sa.Integer(), nullable=False, comment="变更后的积分余额。"),
        sa.Column("experience_after", sa.Integer(), nullable=False, comment="变更后的累计经验。"),
        sa.Column("level_after", sa.Integer(), nullable=False, comment="变更后的用户等级快照。"),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            nullable=True,
            comment="触发该变化的用户 ID；系统触发时为空。",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=160),
            nullable=False,
            comment="幂等键；同一业务事件只允许写入一次流水。",
        ),
        sa.Column("note", sa.String(length=500), nullable=True, comment="可审计备注。"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_user_point_events_idempotency_key"),
        comment="用户积分和经验流水，记录来源、变更值、幂等键与变更后快照。",
    )
    op.create_index("ix_user_point_events_user_id", "user_point_events", ["user_id"])
    op.create_index(
        "ix_user_point_events_user_created",
        "user_point_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_user_point_events_source_created",
        "user_point_events",
        ["source_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_point_events_source_created", table_name="user_point_events")
    op.drop_index("ix_user_point_events_user_created", table_name="user_point_events")
    op.drop_index("ix_user_point_events_user_id", table_name="user_point_events")
    op.drop_table("user_point_events")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("experience_total")
        batch_op.drop_column("points_balance")
