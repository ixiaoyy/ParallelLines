"""add badges trust levels

Revision ID: 0025_badges_trust_levels
Revises: 0024_user_points_experience
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_badges_trust_levels"
down_revision: str | None = "0024_user_points_experience"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "trust_level",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="用户信任等级，独立于角色权限，用于反垃圾、上传和发链接风险控制。默认 0。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "trust_level_changed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最近一次信任等级变化时间；为空表示尚未发生变化。",
            )
        )

    op.create_table(
        "badge_definitions",
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
            "slug",
            sa.String(length=64),
            nullable=False,
            comment="徽章稳定标识，用于自动授予和前端图标映射。",
        ),
        sa.Column("name", sa.String(length=96), nullable=False, comment="徽章显示名称。"),
        sa.Column(
            "description",
            sa.String(length=500),
            nullable=False,
            comment="徽章含义与获得条件说明。",
        ),
        sa.Column(
            "category",
            sa.String(length=48),
            nullable=False,
            comment="徽章分类，如 account、participation、reputation 或 trust。",
        ),
        sa.Column("icon", sa.String(length=24), nullable=False, comment="徽章短图标或符号。"),
        sa.Column(
            "trust_level_required",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="展示或自动授予建议的最低信任等级。",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="徽章是否仍可授予。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_badge_definitions_slug"),
        comment="徽章定义目录，描述可展示徽章和信任等级门槛。",
    )
    op.create_index("ix_badge_definitions_slug", "badge_definitions", ["slug"])

    op.create_table(
        "user_badges",
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
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="获得徽章的用户 ID。"),
        sa.Column("badge_id", sa.BigInteger(), nullable=False, comment="关联徽章定义 ID。"),
        sa.Column(
            "source_type",
            sa.String(length=48),
            nullable=False,
            comment="授予来源类型，如 email_verified、topic_created 或 admin_manual。",
        ),
        sa.Column(
            "source_id",
            sa.String(length=96),
            nullable=True,
            comment="来源对象 ID；系统或人工授予可为空。",
        ),
        sa.Column(
            "granted_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="授予操作者 ID；自动授予时为空或为触发用户。",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="撤销时间；为空表示徽章当前有效。",
        ),
        sa.Column(
            "revoked_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="撤销操作者 ID；用户删除后为空。",
        ),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True, comment="撤销原因。"),
        sa.Column(
            "idempotency_key",
            sa.String(length=180),
            nullable=False,
            comment="幂等键；同一业务事件只允许写入一次徽章授予流水。",
        ),
        sa.Column("note", sa.String(length=500), nullable=True, comment="授予备注。"),
        sa.ForeignKeyConstraint(["badge_id"], ["badge_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_user_badges_idempotency_key"),
        comment="用户徽章授予与撤销流水，保留来源、操作者和幂等键。",
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])
    op.create_index("ix_user_badges_badge_id", "user_badges", ["badge_id"])
    op.create_index("ix_user_badges_user_active", "user_badges", ["user_id", "revoked_at"])
    op.create_index("ix_user_badges_badge_created", "user_badges", ["badge_id", "created_at"])

    op.create_table(
        "user_trust_level_events",
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
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="信任等级发生变化的用户 ID。",
        ),
        sa.Column("previous_level", sa.Integer(), nullable=False, comment="变化前信任等级。"),
        sa.Column("next_level", sa.Integer(), nullable=False, comment="变化后信任等级。"),
        sa.Column(
            "source_type",
            sa.String(length=48),
            nullable=False,
            comment="触发信任重算或人工调整的来源类型。",
        ),
        sa.Column(
            "source_id",
            sa.String(length=96),
            nullable=True,
            comment="来源对象 ID；系统或人工操作可为空。",
        ),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            nullable=True,
            comment="触发该变化的用户 ID；系统触发时为空。",
        ),
        sa.Column("note", sa.String(length=500), nullable=True, comment="变更原因或说明。"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="用户信任等级变更流水，记录自动或人工调整前后快照。",
    )
    op.create_index("ix_user_trust_level_events_user_id", "user_trust_level_events", ["user_id"])
    op.create_index(
        "ix_user_trust_events_user_created",
        "user_trust_level_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_user_trust_events_source",
        "user_trust_level_events",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_trust_events_source", table_name="user_trust_level_events")
    op.drop_index("ix_user_trust_events_user_created", table_name="user_trust_level_events")
    op.drop_index("ix_user_trust_level_events_user_id", table_name="user_trust_level_events")
    op.drop_table("user_trust_level_events")

    op.drop_index("ix_user_badges_badge_created", table_name="user_badges")
    op.drop_index("ix_user_badges_user_active", table_name="user_badges")
    op.drop_index("ix_user_badges_badge_id", table_name="user_badges")
    op.drop_index("ix_user_badges_user_id", table_name="user_badges")
    op.drop_table("user_badges")

    op.drop_index("ix_badge_definitions_slug", table_name="badge_definitions")
    op.drop_table("badge_definitions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("trust_level_changed_at")
        batch_op.drop_column("trust_level")
