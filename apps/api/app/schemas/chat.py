from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.chat import ChatChannel, ChatMessage, ChatPresence
from app.models.user import User


class ChatUserResponse(BaseModel):
    id: str
    username: str
    avatar_url: str | None = None

    @classmethod
    def from_user(cls, user: User) -> ChatUserResponse:
        return cls(id=user.id, username=user.username, avatar_url=user.avatar_url)


class ChatChannelCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    channel_type: Literal["public", "board", "direct"] = "public"
    slug: str | None = Field(default=None, min_length=2, max_length=96)
    board_slug: str | None = Field(default=None, max_length=96)
    participant_usernames: list[str] = Field(default_factory=list, max_length=20)


class ChatChannelResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    channel_type: str
    board_id: str | None = None
    board_slug: str | None = None
    created_by_id: str | None = None
    message_count: int
    member_count: int
    last_message_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_model(
        cls,
        channel: ChatChannel,
        *,
        member_count: int = 0,
    ) -> ChatChannelResponse:
        return cls(
            id=channel.id,
            slug=channel.slug,
            name=channel.name,
            description=channel.description,
            channel_type=channel.channel_type,
            board_id=channel.board_id,
            board_slug=channel.board.slug if channel.board else None,
            created_by_id=channel.created_by_id,
            message_count=channel.message_count,
            member_count=member_count,
            last_message_at=channel.last_message_at,
            created_at=channel.created_at,
        )


class ChatMessageCreateRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=5_000)


class ChatMessageResponse(BaseModel):
    id: str
    channel_id: str
    user: ChatUserResponse
    raw_text: str
    created_at: datetime

    @classmethod
    def from_model(cls, message: ChatMessage) -> ChatMessageResponse:
        return cls(
            id=message.id,
            channel_id=message.channel_id,
            user=ChatUserResponse.from_user(message.user),
            raw_text=message.raw_text,
            created_at=message.created_at,
        )


class ChatMessagePageResponse(BaseModel):
    messages: list[ChatMessageResponse]
    next_before_id: str | None = None
    has_more: bool = False


class ChatPresenceUpdateRequest(BaseModel):
    status: Literal["online", "away"] = "online"
    typing: bool = False


class ChatPresenceResponse(BaseModel):
    channel_id: str
    user: ChatUserResponse
    status: str
    online: bool
    typing: bool
    last_seen_at: datetime
    typing_until: datetime | None = None

    @classmethod
    def from_model(
        cls,
        presence: ChatPresence,
        *,
        now: datetime,
        online_cutoff: datetime,
    ) -> ChatPresenceResponse:
        last_seen_at = presence.last_seen_at
        typing_until = presence.typing_until
        if last_seen_at.tzinfo is None:
            now = now.replace(tzinfo=None)
            online_cutoff = online_cutoff.replace(tzinfo=None)
        return cls(
            channel_id=presence.channel_id,
            user=ChatUserResponse.from_user(presence.user),
            status=presence.status,
            online=last_seen_at >= online_cutoff,
            typing=typing_until is not None and typing_until >= now,
            last_seen_at=last_seen_at,
            typing_until=typing_until,
        )


class ChatStreamResponse(BaseModel):
    messages: list[ChatMessageResponse]
    presence: list[ChatPresenceResponse]
