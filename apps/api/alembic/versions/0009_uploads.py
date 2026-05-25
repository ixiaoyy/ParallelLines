"""add uploads

Revision ID: 0009_uploads
Revises: 0008_board_invitations
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_uploads"
down_revision: str | None = "0008_board_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="上传文件的用户 ID。"),
        sa.Column(
            "board_id",
            sa.BigInteger(),
            nullable=True,
            comment="附件归属版块 ID；临时文件或头像为空。",
        ),
        sa.Column(
            "topic_id",
            sa.BigInteger(),
            nullable=True,
            comment="附件归属主题 ID；临时文件或头像为空。",
        ),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            nullable=True,
            comment="附件归属帖子 ID；临时文件或头像为空。",
        ),
        sa.Column(
            "original_filename",
            sa.String(length=255),
            nullable=False,
            comment="用户上传时的原始文件名，仅用于展示和下载名。",
        ),
        sa.Column(
            "storage_backend",
            sa.String(length=32),
            nullable=False,
            server_default="local",
            comment="文件存储后端：local 或 s3。",
        ),
        sa.Column(
            "storage_key",
            sa.String(length=512),
            nullable=False,
            comment="存储后端内的对象键，唯一且不含本地绝对路径。",
        ),
        sa.Column(
            "media_type",
            sa.String(length=128),
            nullable=False,
            comment="服务端嗅探确认后的 MIME 类型。",
        ),
        sa.Column("byte_size", sa.Integer(), nullable=False, comment="上传文件字节数。"),
        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=False,
            comment="文件内容 SHA-256 摘要，用于去重和审计。",
        ),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default="post_attachment",
            comment="上传用途：post_attachment 或 avatar。",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="temporary",
            comment="上传状态：temporary、attached、avatar 或 deleted。",
        ),
        sa.Column(
            "is_image",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否为可内联展示的图片。",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="临时上传过期时间；为空表示不自动过期。",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="上传软删除时间；为空表示仍可按权限读取。",
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
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_uploads_storage_key"),
        comment="用户上传的头像、帖子图片和附件元数据及存储引用。",
    )
    op.create_index("ix_uploads_user_status", "uploads", ["user_id", "status"], unique=False)
    op.create_index("ix_uploads_post_status", "uploads", ["post_id", "status"], unique=False)
    op.create_index("ix_uploads_board_status", "uploads", ["board_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_uploads_board_status", table_name="uploads")
    op.drop_index("ix_uploads_post_status", table_name="uploads")
    op.drop_index("ix_uploads_user_status", table_name="uploads")
    op.drop_table("uploads")
