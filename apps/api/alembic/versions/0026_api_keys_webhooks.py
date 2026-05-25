"""add api keys webhooks

Revision ID: 0026_api_keys_webhooks
Revises: 0025_badges_trust_levels
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_api_keys_webhooks"
down_revision: str | None = "0025_badges_trust_levels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="记录创建时间（UTC）。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="记录最后更新时间（UTC）。"),
        sa.Column("name", sa.String(length=120), nullable=False, comment="API Key 显示名称。"),
        sa.Column("token_prefix", sa.String(length=24), nullable=False, comment="令牌前缀，用于管理员识别；不用于认证。"),
        sa.Column("token_hash", sa.String(length=128), nullable=False, comment="高熵 API Key 的 SHA-256 哈希；不保存明文令牌。"),
        sa.Column("scopes", sa.JSON(), nullable=False, comment="允许访问的作用域数组；为空表示不能访问受保护接口。"),
        sa.Column("key_type", sa.String(length=32), nullable=False, server_default="admin", comment="Key 类型：admin 或 personal。"),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True, comment="个人令牌所属用户；系统级管理员令牌可为空。"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True, comment="创建该 Key 的管理员或用户 ID；删除后为空。"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最近一次认证成功时间；为空表示从未使用。"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="过期时间；为空表示不自动过期。"),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True, comment="禁用时间；为空表示仍可使用。"),
        sa.Column("disabled_by_id", sa.BigInteger(), nullable=True, comment="禁用操作者 ID；为空表示未禁用或用户已删除。"),
        sa.Column("note", sa.String(length=500), nullable=True, comment="管理员备注。"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["disabled_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_api_keys_token_hash"),
        comment="外部系统 API Key 元数据，仅保存令牌哈希、作用域、所有者和禁用状态。",
    )
    op.create_index("ix_api_keys_token_prefix", "api_keys", ["token_prefix"])
    op.create_index("ix_api_keys_created_by", "api_keys", ["created_by_id", "created_at"])
    op.create_index("ix_api_keys_owner", "api_keys", ["owner_user_id", "created_at"])
    op.create_index("ix_api_keys_disabled", "api_keys", ["disabled_at"])

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="记录创建时间（UTC）。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="记录最后更新时间（UTC）。"),
        sa.Column("name", sa.String(length=120), nullable=False, comment="Webhook 端点显示名称。"),
        sa.Column("url", sa.String(length=1024), nullable=False, comment="接收 Webhook 的 HTTPS/HTTP URL。"),
        sa.Column("secret", sa.String(length=96), nullable=False, comment="出站签名密钥；仅创建时返回给管理员，后续接口不明文展示。"),
        sa.Column("events", sa.JSON(), nullable=False, comment="订阅事件数组，如 topic.created、post.created 或 moderation.flag_created。"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="端点是否启用。"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True, comment="创建该端点的管理员 ID；删除后为空。"),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True, comment="禁用时间；为空表示仍启用。"),
        sa.Column("disabled_by_id", sa.BigInteger(), nullable=True, comment="禁用操作者 ID；为空表示未禁用或用户已删除。"),
        sa.Column("note", sa.String(length=500), nullable=True, comment="管理员备注。"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["disabled_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="管理员配置的出站 Webhook 端点、订阅事件和签名密钥。",
    )
    op.create_index("ix_webhook_endpoints_active", "webhook_endpoints", ["active", "created_at"])
    op.create_index("ix_webhook_endpoints_created_by", "webhook_endpoints", ["created_by_id", "created_at"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="主键 ID。"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="记录创建时间（UTC）。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="记录最后更新时间（UTC）。"),
        sa.Column("endpoint_id", sa.BigInteger(), nullable=False, comment="目标 Webhook 端点 ID。"),
        sa.Column("event_type", sa.String(length=80), nullable=False, comment="投递事件类型。"),
        sa.Column("payload", sa.JSON(), nullable=False, comment="发送给接收方的 JSON 载荷快照。"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="投递状态：pending、retrying、succeeded、failed 或 disabled。"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0", comment="已尝试投递次数。"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3", comment="最大投递尝试次数。"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True, comment="下一次重试时间；无需重试时为空。"),
        sa.Column("last_status_code", sa.Integer(), nullable=True, comment="接收方最近一次 HTTP 状态码；网络错误时为空。"),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最近一次失败摘要。"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True, comment="成功投递时间；未成功时为空。"),
        sa.Column("response_body_excerpt", sa.Text(), nullable=True, comment="接收方响应正文安全截断摘录。"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["webhook_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Webhook 投递流水，记录事件载荷、尝试次数、响应和重试状态。",
    )
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_endpoint_created", "webhook_deliveries", ["endpoint_id", "created_at"])
    op.create_index("ix_webhook_deliveries_status_next", "webhook_deliveries", ["status", "next_attempt_at"])
    op.create_index("ix_webhook_deliveries_event_created", "webhook_deliveries", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_event_created", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status_next", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_created", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhook_endpoints_created_by", table_name="webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_active", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
    op.drop_index("ix_api_keys_disabled", table_name="api_keys")
    op.drop_index("ix_api_keys_owner", table_name="api_keys")
    op.drop_index("ix_api_keys_created_by", table_name="api_keys")
    op.drop_index("ix_api_keys_token_prefix", table_name="api_keys")
    op.drop_table("api_keys")
