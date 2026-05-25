from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.forum import Board
    from app.models.user import User

ChatChannelType = Literal["public", "board", "direct"]
ChatMemberRole = Literal["owner", "member"]
ChatPresenceStatus = Literal["online", "away"]


class ChatChannel(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_channels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_chat_channels_slug"),
        Index("ix_chat_channels_type_last_message", "channel_type", "last_message_at"),
        Index("ix_chat_channels_board", "board_id"),
        {"comment": "实时聊天频道，支持公共频道、版块频道和成员直聊频道。"},
    )

    slug: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        comment="频道稳定短标识；公共和版块频道可用于 URL 或管理定位。",
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, comment="频道显示名称。")
    description: Mapped[str | None] = mapped_column(
        Text,
        comment="频道说明；为空表示不展示说明。",
    )
    channel_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="public",
        comment="频道类型：public、board 或 direct。",
    )
    board_id: Mapped[str | None] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"),
        comment="版块频道关联的版块 ID；非版块频道为空。",
    )
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="创建频道的用户 ID；用户删除后为空。",
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="频道内未删除消息数量缓存。",
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="最后一条消息时间；为空表示尚无消息。",
    )

    board: Mapped[Board | None] = relationship("Board", lazy="selectin")
    creator: Mapped[User | None] = relationship("User", lazy="selectin")


class ChatChannelMember(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_channel_members"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_chat_channel_members_channel_user"),
        Index("ix_chat_channel_members_user_created", "user_id", "created_at"),
        {"comment": "聊天频道成员关系，用于直聊频道和成员级权限边界。"},
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False,
        comment="聊天频道 ID。",
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="频道成员用户 ID。",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="member",
        comment="成员角色：owner 或 member。",
    )
    last_read_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        comment="该成员最后已读消息 ID；为空表示未同步已读位置。",
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="该成员最后阅读频道时间；为空表示尚未阅读。",
    )

    channel: Mapped[ChatChannel] = relationship("ChatChannel", lazy="selectin")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id], lazy="selectin")


class ChatMessage(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_channel_created", "channel_id", "created_at"),
        Index("ix_chat_messages_user_created", "user_id", "created_at"),
        {"comment": "聊天频道消息，保留原始文本并通过频道权限控制读取。"},
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False,
        comment="消息所属聊天频道 ID。",
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发送消息的用户 ID；账号匿名化后继续指向匿名用户。",
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息原始文本；展示层负责转义，不保存 HTML。",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="软删除时间；为空表示消息可见。",
    )

    channel: Mapped[ChatChannel] = relationship("ChatChannel", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")


class ChatPresence(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_presence"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_chat_presence_channel_user"),
        Index("ix_chat_presence_channel_seen", "channel_id", "last_seen_at"),
        {"comment": "聊天频道在线状态和输入状态快照，属于可过期的派生状态。"},
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("chat_channels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Presence 所属聊天频道 ID。",
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="在线状态对应用户 ID。",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="online",
        comment="在线状态：online 或 away。",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="最后一次心跳时间；超过 TTL 视为离线。",
    )
    typing_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="正在输入状态有效截止时间；为空表示未在输入。",
    )

    channel: Mapped[ChatChannel] = relationship("ChatChannel", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")
