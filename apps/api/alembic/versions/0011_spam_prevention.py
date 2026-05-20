"""add spam prevention tables

Revision ID: 0011_spam_prevention
Revises: 0010_account_security
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_spam_prevention"
down_revision: str | None = "0010_account_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "scope",
            sa.String(length=64),
            nullable=False,
            comment="频控场景，如 register:ip 或 topic:user。",
        ),
        sa.Column(
            "identity_type",
            sa.String(length=32),
            nullable=False,
            comment="频控主体类型：user、ip、email 或 account。",
        ),
        sa.Column(
            "identity_key",
            sa.String(length=255),
            nullable=False,
            comment="频控主体归一化键。",
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=True,
            comment="触发频控事件的用户 ID；匿名路径为空。",
        ),
        sa.Column(
            "ip_address",
            sa.String(length=64),
            nullable=True,
            comment="触发频控事件的请求来源 IP。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="频控事件发生时间。",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="写操作频控事件，用于用户/IP/邮箱等维度的滑动窗口计数。",
    )
    op.create_index(
        "ix_rate_limit_events_scope_created",
        "rate_limit_events",
        ["scope", "identity_key", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rate_limit_events_user_created",
        "rate_limit_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rate_limit_events_ip_created",
        "rate_limit_events",
        ["ip_address", "created_at"],
        unique=False,
    )

    op.create_table(
        "screened_rules",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "kind", sa.String(length=32), nullable=False, comment="规则类型：email、ip 或 url。"
        ),
        sa.Column(
            "value", sa.String(length=255), nullable=False, comment="管理员输入的原始屏蔽值。"
        ),
        sa.Column(
            "normalized_value",
            sa.String(length=255),
            nullable=False,
            comment="用于匹配的归一化值。",
        ),
        sa.Column(
            "action",
            sa.String(length=32),
            nullable=False,
            server_default="block",
            comment="命中后的处置动作：block 或 silence。",
        ),
        sa.Column("note", sa.Text(), nullable=True, comment="管理员备注；为空表示无备注。"),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="规则是否启用。",
        ),
        sa.Column(
            "created_by_id",
            sa.String(length=36),
            nullable=True,
            comment="创建规则的管理员 ID。",
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
        sa.UniqueConstraint("kind", "normalized_value", name="uq_screened_rules_kind_value"),
        comment="邮箱、IP、URL 屏蔽名单规则及自动处置动作。",
    )
    op.create_index("ix_screened_rules_kind", "screened_rules", ["kind"], unique=False)

    op.create_table(
        "spam_actions",
        sa.Column("id", sa.String(length=36), nullable=False, comment="主键 UUID。"),
        sa.Column(
            "kind",
            sa.String(length=64),
            nullable=False,
            comment="自动处置类型：rate_limit、screened_rule 或 new_user_screening。",
        ),
        sa.Column(
            "action",
            sa.String(length=32),
            nullable=False,
            comment="自动处置动作：block 或 silence。",
        ),
        sa.Column("reason", sa.String(length=128), nullable=False, comment="触发处置的原因摘要。"),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=True,
            comment="被处置用户 ID；匿名注册/登录路径为空。",
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True, comment="触发处置的来源 IP。"),
        sa.Column(
            "email", sa.String(length=255), nullable=True, comment="命中的邮箱；非邮箱规则为空。"
        ),
        sa.Column(
            "url", sa.String(length=1024), nullable=True, comment="命中的 URL；非 URL 规则为空。"
        ),
        sa.Column(
            "screened_rule_id",
            sa.String(length=36),
            nullable=True,
            comment="命中的屏蔽规则 ID；频控或新用户筛查为空。",
        ),
        sa.Column(
            "data",
            sa.JSON(),
            nullable=False,
            comment="处置上下文结构化数据，不包含密码或令牌。",
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
        sa.ForeignKeyConstraint(["screened_rule_id"], ["screened_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="反垃圾系统自动拦截、禁言和频控处置记录。",
    )
    op.create_index(
        "ix_spam_actions_user_created",
        "spam_actions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_spam_actions_rule_created",
        "spam_actions",
        ["screened_rule_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_spam_actions_kind_created",
        "spam_actions",
        ["kind", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_spam_actions_kind_created", table_name="spam_actions")
    op.drop_index("ix_spam_actions_rule_created", table_name="spam_actions")
    op.drop_index("ix_spam_actions_user_created", table_name="spam_actions")
    op.drop_table("spam_actions")
    op.drop_index("ix_screened_rules_kind", table_name="screened_rules")
    op.drop_table("screened_rules")
    op.drop_index("ix_rate_limit_events_ip_created", table_name="rate_limit_events")
    op.drop_index("ix_rate_limit_events_user_created", table_name="rate_limit_events")
    op.drop_index("ix_rate_limit_events_scope_created", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
