"""add revocable cross-product access grants

Revision ID: 0068_product_access_grants
Revises: 0067_add_private_space_board
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0068_product_access_grants"
down_revision: str | None = "0067_add_private_space_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persistent, versioned, and revocable product access grants.

    Key parameters: none. Return value: none. Side effect: creates one table and
    two lookup indexes, then seeds active forum administrators for rollout continuity.
    """

    op.create_table(
        "product_access_grants",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "product",
            sa.String(length=32),
            nullable=False,
            comment="外部产品稳定标识；首个接入值为 fablespace。",
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="获得授权的论坛用户 ID。"),
        sa.Column(
            "access_level",
            sa.String(length=32),
            nullable=False,
            comment="产品权限等级：access、creator、operator 或 admin。",
        ),
        sa.Column(
            "granted_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="最近一次授予或重新授予该资格的管理员 ID。",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="授权到期时间（UTC）；为空表示不自动到期。",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="授权撤销时间（UTC）；为空表示未撤销。",
        ),
        sa.Column(
            "revoked_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="最近一次撤销授权的管理员 ID。",
        ),
        sa.Column(
            "authorization_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="授权状态版本；每次有效变更递增，供外部会话续验。",
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
        sa.ForeignKeyConstraint(["granted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product",
            "user_id",
            name="uq_product_access_grants_product_user",
        ),
        comment="跨产品用户资格授权，保存权限等级、期限、撤销与会话续验版本。",
    )
    op.create_index(
        "ix_product_access_grants_product_state",
        "product_access_grants",
        ["product", "revoked_at", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_product_access_grants_user_product",
        "product_access_grants",
        ["user_id", "product"],
        unique=False,
    )

    users = sa.table(
        "users",
        sa.column("id", sa.BigInteger()),
        sa.column("role", sa.String(length=32)),
        sa.column("status", sa.String(length=32)),
    )
    grants = sa.table(
        "product_access_grants",
        sa.column("product", sa.String(length=32)),
        sa.column("user_id", sa.BigInteger()),
        sa.column("access_level", sa.String(length=32)),
        sa.column("granted_by_id", sa.BigInteger()),
        sa.column("expires_at", sa.DateTime(timezone=True)),
        sa.column("revoked_at", sa.DateTime(timezone=True)),
        sa.column("revoked_by_id", sa.BigInteger()),
        sa.column("authorization_version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    seeded_at = datetime.now(UTC).replace(tzinfo=None)
    op.get_bind().execute(
        grants.insert().from_select(
            [
                "product",
                "user_id",
                "access_level",
                "granted_by_id",
                "expires_at",
                "revoked_at",
                "revoked_by_id",
                "authorization_version",
                "created_at",
                "updated_at",
            ],
            sa.select(
                sa.literal("fablespace"),
                users.c.id,
                sa.literal("admin"),
                sa.null(),
                sa.null(),
                sa.null(),
                sa.null(),
                sa.literal(1),
                sa.literal(seeded_at, type_=sa.DateTime(timezone=True)),
                sa.literal(seeded_at, type_=sa.DateTime(timezone=True)),
            ).where(users.c.role == "admin", users.c.status == "active"),
        )
    )


def downgrade() -> None:
    """Remove cross-product grants when rolling back this schema revision.

    Key parameters: none. Return value: none. Side effect: drops grant indexes and
    the grant table, including its authorization history.
    """

    op.drop_index(
        "ix_product_access_grants_user_product",
        table_name="product_access_grants",
    )
    op.drop_index(
        "ix_product_access_grants_product_state",
        table_name="product_access_grants",
    )
    op.drop_table("product_access_grants")
