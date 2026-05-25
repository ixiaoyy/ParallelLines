"""add user relationships and private messages

Revision ID: 0021_user_social_pm
Revises: 0020_notification_quiet_hours
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_user_social_pm"
down_revision: str | None = "0020_notification_quiet_hours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column(
            "topic_type",
            sa.String(length=32),
            nullable=False,
            server_default="regular",
            comment="主题类型：regular 表示公开/版块主题，private_message 表示私信主题。",
        ),
    )
    op.add_column(
        "topics",
        sa.Column(
            "visibility",
            sa.String(length=32),
            nullable=False,
            server_default="public",
            comment="主题可见性：public 表示沿用版块可见性，private_message 表示仅私信参与者可见。",
        ),
    )
    op.create_index("ix_topics_visibility_last_posted", "topics", ["visibility", "last_posted_at"])

    op.create_table(
        "user_relationships",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="关系记录 ID。"),
        sa.Column(
            "actor_user_id",
            sa.BigInteger(),
            nullable=False,
            comment="发起关系的用户 ID。",
        ),
        sa.Column(
            "target_user_id",
            sa.BigInteger(),
            nullable=False,
            comment="被关注、忽略或屏蔽的目标用户 ID。",
        ),
        sa.Column(
            "relationship_type",
            sa.String(length=32),
            nullable=False,
            comment="用户关系类型：follow、ignore 或 block。",
        ),
        sa.Column(
            "note",
            sa.String(length=255),
            nullable=True,
            comment="关系备注；为空表示未填写。",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "actor_user_id",
            "target_user_id",
            "relationship_type",
            name="uq_user_relationships_actor_target_type",
        ),
        comment="用户之间的关注、忽略和屏蔽关系。",
    )
    op.create_index(
        "ix_user_relationships_actor_type",
        "user_relationships",
        ["actor_user_id", "relationship_type"],
    )
    op.create_index(
        "ix_user_relationships_target_type",
        "user_relationships",
        ["target_user_id", "relationship_type"],
    )

    op.create_table(
        "private_message_participants",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="私信参与记录 ID。"),
        sa.Column("topic_id", sa.BigInteger(), nullable=False, comment="私信主题 ID。"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="参与私信的用户 ID。"),
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="participant",
            comment="私信参与者角色：owner 或 participant。",
        ),
        sa.Column(
            "last_read_post_number",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="该参与者已读到的最高楼层编号。",
        ),
        sa.Column(
            "muted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="该参与者是否静音此私信主题。",
        ),
        sa.Column(
            "last_read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="该参与者最后阅读私信的时间；为空表示尚未阅读。",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="加入私信时间。",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="更新时间。"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "topic_id",
            "user_id",
            name="uq_private_message_participants_topic_user",
        ),
        comment="私信主题参与者及其已读状态。",
    )
    op.create_index(
        "ix_private_message_participants_user_created",
        "private_message_participants",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_private_message_participants_topic_role",
        "private_message_participants",
        ["topic_id", "role"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_private_message_participants_topic_role",
        table_name="private_message_participants",
    )
    op.drop_index(
        "ix_private_message_participants_user_created",
        table_name="private_message_participants",
    )
    op.drop_table("private_message_participants")
    op.drop_index("ix_user_relationships_target_type", table_name="user_relationships")
    op.drop_index("ix_user_relationships_actor_type", table_name="user_relationships")
    op.drop_table("user_relationships")
    op.drop_index("ix_topics_visibility_last_posted", table_name="topics")
    op.drop_column("topics", "visibility")
    op.drop_column("topics", "topic_type")
