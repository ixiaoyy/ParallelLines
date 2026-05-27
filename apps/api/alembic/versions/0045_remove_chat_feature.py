"""remove retired chat tables

Revision ID: 0045_remove_chat_feature
Revises: 0044_cleanup_demo_users
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0045_remove_chat_feature"
down_revision: str | None = "0044_cleanup_demo_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHAT_TABLES = (
    "chat_presence",
    "chat_channel_members",
    "chat_messages",
    "chat_channels",
)


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in CHAT_TABLES:
        if table_name in existing_tables:
            op.drop_table(table_name)


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "chat_channels" not in existing_tables:
        op.create_table(
            "chat_channels",
            sa.Column("id", sa.BigInteger(), primary_key=True, comment="聊天频道 ID。"),
            sa.Column(
                "slug",
                sa.String(length=96),
                nullable=False,
                comment="频道稳定短标识；公共和版块频道可用于 URL 或管理定位。",
            ),
            sa.Column("name", sa.String(length=120), nullable=False, comment="频道显示名称。"),
            sa.Column(
                "description",
                sa.Text(),
                nullable=True,
                comment="频道说明；为空表示不展示说明。",
            ),
            sa.Column(
                "channel_type",
                sa.String(length=32),
                nullable=False,
                server_default="public",
                comment="频道类型：public、board 或 direct。",
            ),
            sa.Column(
                "board_id",
                sa.BigInteger(),
                nullable=True,
                comment="版块频道关联的版块 ID；非版块频道为空。",
            ),
            sa.Column(
                "created_by_id",
                sa.BigInteger(),
                nullable=True,
                comment="创建频道的用户 ID；用户删除后为空。",
            ),
            sa.Column(
                "message_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="频道内未删除消息数量缓存。",
            ),
            sa.Column(
                "last_message_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最后一条消息时间；为空表示尚无消息。",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="创建时间。",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="更新时间。",
            ),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("slug", name="uq_chat_channels_slug"),
            comment="实时聊天频道，支持公共频道、版块频道和成员直聊频道。",
        )
        op.create_index(
            "ix_chat_channels_type_last_message",
            "chat_channels",
            ["channel_type", "last_message_at"],
        )
        op.create_index("ix_chat_channels_board", "chat_channels", ["board_id"])

    if "chat_messages" not in existing_tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.BigInteger(), primary_key=True, comment="聊天消息 ID。"),
            sa.Column("channel_id", sa.BigInteger(), nullable=False, comment="聊天频道 ID。"),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                nullable=False,
                comment="发送消息的用户 ID；账号匿名化后继续指向匿名用户。",
            ),
            sa.Column(
                "raw_text",
                sa.Text(),
                nullable=False,
                comment="消息原始文本；展示层负责转义，不保存 HTML。",
            ),
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="软删除时间；为空表示消息可见。",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="创建时间。",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="更新时间。",
            ),
            sa.ForeignKeyConstraint(["channel_id"], ["chat_channels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            comment="聊天频道消息，保留原始文本并通过频道权限控制读取。",
        )
        op.create_index(
            "ix_chat_messages_channel_created",
            "chat_messages",
            ["channel_id", "created_at"],
        )
        op.create_index(
            "ix_chat_messages_user_created",
            "chat_messages",
            ["user_id", "created_at"],
        )

    if "chat_channel_members" not in existing_tables:
        op.create_table(
            "chat_channel_members",
            sa.Column("id", sa.BigInteger(), primary_key=True, comment="聊天频道成员记录 ID。"),
            sa.Column("channel_id", sa.BigInteger(), nullable=False, comment="聊天频道 ID。"),
            sa.Column("user_id", sa.BigInteger(), nullable=False, comment="频道成员用户 ID。"),
            sa.Column(
                "role",
                sa.String(length=32),
                nullable=False,
                server_default="member",
                comment="成员角色：owner 或 member。",
            ),
            sa.Column(
                "last_read_message_id",
                sa.BigInteger(),
                nullable=True,
                comment="该成员最后已读消息 ID；为空表示未同步已读位置。",
            ),
            sa.Column(
                "last_read_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="该成员最后阅读频道时间；为空表示尚未阅读。",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="创建时间。",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="更新时间。",
            ),
            sa.ForeignKeyConstraint(["channel_id"], ["chat_channels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["last_read_message_id"],
                ["chat_messages.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "channel_id",
                "user_id",
                name="uq_chat_channel_members_channel_user",
            ),
            comment="聊天频道成员关系，用于直聊频道和成员级权限边界。",
        )
        op.create_index(
            "ix_chat_channel_members_user_created",
            "chat_channel_members",
            ["user_id", "created_at"],
        )

    if "chat_presence" not in existing_tables:
        op.create_table(
            "chat_presence",
            sa.Column("id", sa.BigInteger(), primary_key=True, comment="Presence 记录 ID。"),
            sa.Column("channel_id", sa.BigInteger(), nullable=False, comment="聊天频道 ID。"),
            sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户 ID。"),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="online",
                comment="在线状态：online 或 away。",
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="最后一次心跳时间；超过 TTL 视为离线。",
            ),
            sa.Column(
                "typing_until",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="正在输入状态有效截止时间；为空表示未在输入。",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="创建时间。",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                comment="更新时间。",
            ),
            sa.ForeignKeyConstraint(["channel_id"], ["chat_channels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("channel_id", "user_id", name="uq_chat_presence_channel_user"),
            comment="聊天频道在线状态和输入状态快照，属于可过期的派生状态。",
        )
        op.create_index(
            "ix_chat_presence_channel_seen",
            "chat_presence",
            ["channel_id", "last_seen_at"],
        )
