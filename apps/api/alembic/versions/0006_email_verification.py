"""create email verification codes

Revision ID: 0006_email_verification
Revises: 0005_schema_comments
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_email_verification"
down_revision: str | None = "0005_schema_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="主键 UUID。"),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="待验证用户 ID。"),
        sa.Column("email", sa.String(length=255), nullable=False, comment="接收验证码的邮箱地址。"),
        sa.Column(
            "code_hash",
            sa.String(length=128),
            nullable=False,
            comment="验证码的不可逆哈希值。",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="验证码邮件发送时间。",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="验证码失效时间。",
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="验证码成功使用时间；为空表示未使用。",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            comment="该验证码已被尝试校验的次数。",
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
        comment="邮箱注册验证码记录，用于账号激活和重发限流。",
    )
    op.create_index(
        "ix_email_verification_codes_user_sent",
        "email_verification_codes",
        ["user_id", "sent_at"],
    )
    op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])


def downgrade() -> None:
    op.drop_index("ix_email_verification_codes_email", table_name="email_verification_codes")
    op.drop_index(
        "ix_email_verification_codes_user_sent",
        table_name="email_verification_codes",
    )
    op.drop_table("email_verification_codes")
