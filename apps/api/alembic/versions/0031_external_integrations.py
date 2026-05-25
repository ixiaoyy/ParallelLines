"""add external integrations

Revision ID: 0031_external_integrations
Revises: 0030_calendar_events
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031_external_integrations"
down_revision: str | None = "0030_calendar_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_integrations",
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
            "provider",
            sa.String(length=32),
            nullable=False,
            comment="外部集成 provider 标识，如 github、zendesk 或 patreon。",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="该 provider 是否启用。",
        ),
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            comment="provider 配置 JSON；响应层会隐藏 webhook_secret、api_token 等敏感键。",
        ),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="创建配置的管理员 ID；用户删除后为空。",
        ),
        sa.Column(
            "updated_by_id",
            sa.BigInteger(),
            nullable=True,
            comment="最后更新配置的管理员 ID；用户删除后为空。",
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最近一次健康检查或配置保存时间；为空表示未检查。",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="最近一次集成处理错误摘要；为空表示无已知错误。",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", name="uq_external_integrations_provider"),
        comment="外部 provider 集成配置，保存启用状态、非公开配置和健康检查状态。",
    )
    op.create_index(
        "ix_external_integrations_enabled", "external_integrations", ["enabled", "updated_at"]
    )

    op.create_table(
        "external_integration_events",
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
            "provider", sa.String(length=32), nullable=False, comment="事件来源 provider 标识。"
        ),
        sa.Column(
            "event_id",
            sa.String(length=128),
            nullable=False,
            comment="provider 投递事件 ID，用于幂等处理。",
        ),
        sa.Column(
            "event_type",
            sa.String(length=80),
            nullable=False,
            comment="provider 事件类型，如 GitHub issues。",
        ),
        sa.Column(
            "action",
            sa.String(length=80),
            nullable=True,
            comment="provider 事件动作，如 opened、edited；为空表示未提供。",
        ),
        sa.Column(
            "payload", sa.JSON(), nullable=False, comment="入站事件安全截断载荷，不包含密钥。"
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
            comment="处理状态：pending、processed、ignored、retrying 或 failed。",
        ),
        sa.Column(
            "signature_valid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="入站 webhook 是否通过 HMAC 验签。",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="集成事件已重试次数。",
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            nullable=False,
            server_default="3",
            comment="最大处理重试次数。",
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="下一次重试时间；无需重试时为空。",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="事件成功处理或忽略时间；未完成时为空。",
        ),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最近一次处理失败摘要。"),
        sa.Column(
            "linked_resource_type",
            sa.String(length=80),
            nullable=True,
            comment="关联外部资源类型，如 github_issue。",
        ),
        sa.Column(
            "linked_resource_id",
            sa.String(length=128),
            nullable=True,
            comment="关联外部资源 ID 或编号。",
        ),
        sa.Column("external_url", sa.String(length=1024), nullable=True, comment="外部资源 URL。"),
        sa.Column("title", sa.String(length=500), nullable=True, comment="外部资源展示标题。"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_external_integration_event"),
        comment="外部 provider 入站事件流水，记录验签、处理、重试和可展开资源摘要。",
    )
    op.create_index(
        "ix_external_integration_events_provider_created",
        "external_integration_events",
        ["provider", "created_at"],
    )
    op.create_index(
        "ix_external_integration_events_status_next",
        "external_integration_events",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_integration_events_status_next", table_name="external_integration_events"
    )
    op.drop_index(
        "ix_external_integration_events_provider_created", table_name="external_integration_events"
    )
    op.drop_table("external_integration_events")
    op.drop_index("ix_external_integrations_enabled", table_name="external_integrations")
    op.drop_table("external_integrations")
