"""add admin site settings

Revision ID: 0014_admin_site_settings
Revises: 0013_topic_lifecycle
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_admin_site_settings"
down_revision: str | None = "0013_topic_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column(
            "key",
            sa.String(length=96),
            nullable=False,
            comment="设置键名，作为 API 与前端读取的稳定标识。",
        ),
        sa.Column(
            "value",
            sa.JSON(),
            nullable=False,
            comment="设置值，按 data_type 保存为 JSON 标量或对象。",
        ),
        sa.Column(
            "data_type",
            sa.String(length=32),
            nullable=False,
            comment="设置值类型：string、boolean、integer 或 json。",
        ),
        sa.Column(
            "category",
            sa.String(length=48),
            nullable=False,
            comment="设置分类，如 brand、access 或 uploads。",
        ),
        sa.Column("description", sa.Text(), nullable=False, comment="后台展示的设置说明。"),
        sa.Column(
            "public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否可通过公开站点设置接口暴露给前端。",
        ),
        sa.Column(
            "updated_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="最后修改该设置的管理员 ID；系统默认值为空。",
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
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_site_settings_key"),
        comment="站点级可运营配置，包括品牌、注册开关和上传限制。",
    )
    op.create_index(
        "ix_site_settings_category",
        "site_settings",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_settings_category", table_name="site_settings")
    op.drop_table("site_settings")
