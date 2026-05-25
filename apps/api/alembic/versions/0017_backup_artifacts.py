"""add backup artifacts

Revision ID: 0017_backup_artifacts
Revises: 0016_email_notifications
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_backup_artifacts"
down_revision: str | None = "0016_email_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_artifacts",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            comment="归档类型：site_backup、site_export 或 user_export。",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="归档状态：queued、running、succeeded、failed 或 deleted。",
        ),
        sa.Column("filename", sa.String(length=255), nullable=False, comment="下载文件名。"),
        sa.Column(
            "storage_backend",
            sa.String(length=32),
            nullable=False,
            comment="归档存储后端，当前为 local。",
        ),
        sa.Column(
            "storage_key",
            sa.String(length=512),
            nullable=True,
            comment="归档在存储后端内的对象键；未生成或删除时为空。",
        ),
        sa.Column("byte_size", sa.Integer(), nullable=True, comment="归档文件字节数。"),
        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=True,
            comment="归档文件 SHA-256 校验和。",
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            comment="归档元数据、表计数和安全摘录；不包含密码或令牌明文。",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True, comment="备份失败原因摘要。"),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="触发备份或导出的管理员 ID；用户删除后为空。",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="归档成功、失败或删除完成时间；队列中为空。",
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="备份、导出归档元数据、校验和和状态记录。",
    )
    op.create_index(
        "ix_backup_artifacts_kind_created",
        "backup_artifacts",
        ["kind", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_backup_artifacts_status_created",
        "backup_artifacts",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_backup_artifacts_status_created", table_name="backup_artifacts")
    op.drop_index("ix_backup_artifacts_kind_created", table_name="backup_artifacts")
    op.drop_table("backup_artifacts")
