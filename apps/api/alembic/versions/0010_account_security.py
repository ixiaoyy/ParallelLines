"""add account security tables

Revision ID: 0010_account_security
Revises: 0009_uploads
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_account_security"
down_revision: str | None = "0009_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "two_factor_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否启用 TOTP 二次验证。",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "two_factor_secret",
            sa.String(length=64),
            nullable=True,
            comment="TOTP Base32 密钥；为空表示未完成启用。",
        ),
    )
    op.create_table(
        "user_security_tokens",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="安全令牌所属用户 ID。"),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            comment="令牌用途：password_reset 或 email_change。",
        ),
        sa.Column(
            "token_hash",
            sa.String(length=128),
            nullable=False,
            comment="一次性令牌的不可逆哈希值。",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=True,
            comment="令牌发送目标邮箱；为空表示使用用户当前邮箱。",
        ),
        sa.Column(
            "payload",
            sa.Text(),
            nullable=True,
            comment="令牌附带的 JSON 数据，如新邮箱地址。",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, comment="令牌发送时间。"),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False, comment="令牌失效时间。"
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="令牌成功使用时间；为空表示未使用。",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="该令牌已被尝试校验的次数。",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_security_tokens_token_hash"),
        comment="账号找回、邮箱变更等一次性安全令牌记录。",
    )
    op.create_index(
        "ix_user_security_tokens_user_purpose",
        "user_security_tokens",
        ["user_id", "purpose"],
        unique=False,
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="会话所属用户 ID。"),
        sa.Column(
            "refresh_token_hash",
            sa.String(length=128),
            nullable=False,
            comment="刷新令牌的不可逆哈希值，用于撤销校验。",
        ),
        sa.Column(
            "user_agent",
            sa.String(length=256),
            nullable=True,
            comment="登录设备/浏览器 User-Agent 摘要。",
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True, comment="登录请求来源 IP。"),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="该会话最后活跃时间。",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="会话撤销时间；为空表示仍有效。",
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
        sa.PrimaryKeyConstraint("id"),
        comment="用户登录会话、刷新令牌哈希和设备撤销状态。",
    )
    op.create_index(
        "ix_user_sessions_user_revoked",
        "user_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )
    op.create_table(
        "user_recovery_codes",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="恢复码所属用户 ID。"),
        sa.Column(
            "code_hash", sa.String(length=128), nullable=False, comment="恢复码的不可逆哈希值。"
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="恢复码使用时间；为空表示仍可使用。",
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
        sa.PrimaryKeyConstraint("id"),
        comment="TOTP 二次验证恢复码的哈希与使用状态。",
    )
    op.create_index(
        "ix_user_recovery_codes_user_used",
        "user_recovery_codes",
        ["user_id", "used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_recovery_codes_user_used", table_name="user_recovery_codes")
    op.drop_table("user_recovery_codes")
    op.drop_index("ix_user_sessions_user_revoked", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_user_security_tokens_user_purpose", table_name="user_security_tokens")
    op.drop_table("user_security_tokens")
    op.drop_column("users", "two_factor_secret")
    op.drop_column("users", "two_factor_enabled")
