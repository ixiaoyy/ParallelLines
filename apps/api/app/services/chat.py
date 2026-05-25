from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import utcnow
from app.models.chat import ChatChannel, ChatChannelMember, ChatMessage, ChatPresence
from app.models.forum import Board, BoardMember
from app.models.social import UserRelationship
from app.models.user import User
from app.schemas.chat import (
    ChatChannelCreateRequest,
    ChatChannelResponse,
    ChatMessageCreateRequest,
    ChatMessagePageResponse,
    ChatMessageResponse,
    ChatPresenceResponse,
    ChatPresenceUpdateRequest,
    ChatStreamResponse,
)
from app.services.forum import escape_like, slugify

PRESENCE_TTL_SECONDS = 120
TYPING_TTL_SECONDS = 8


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_channels(self, current_user: User) -> list[ChatChannelResponse]:
        channels = list(
            await self.session.scalars(
                select(ChatChannel)
                .options(selectinload(ChatChannel.board))
                .order_by(ChatChannel.last_message_at.desc().nullslast(), ChatChannel.created_at)
            )
        )
        accessible: list[ChatChannel] = []
        for channel in channels:
            if await self._can_access_channel(channel, current_user):
                accessible.append(channel)
        member_counts = await self._member_counts([channel.id for channel in accessible])
        return [
            ChatChannelResponse.from_model(
                channel,
                member_count=member_counts.get(channel.id, 0),
            )
            for channel in accessible
        ]

    async def create_channel(
        self,
        payload: ChatChannelCreateRequest,
        current_user: User,
    ) -> ChatChannelResponse:
        board: Board | None = None
        members: list[User] = [current_user]
        if payload.channel_type == "board":
            if not payload.board_slug:
                raise ValidationError("chat_board_required", "Board slug is required.")
            board = await self._get_board(payload.board_slug)
            if not await self._can_access_board(board, current_user):
                raise NotFoundError("board_not_found", "Board not found")
        elif payload.channel_type == "direct":
            recipients = await self._resolve_direct_recipients(
                payload.participant_usernames,
                current_user,
            )
            await self._ensure_direct_allowed(current_user, recipients)
            members.extend(recipients)

        channel = ChatChannel(
            slug=await self._unique_channel_slug(payload.slug or payload.name),
            name=payload.name.strip(),
            description=(payload.description or "").strip() or None,
            channel_type=payload.channel_type,
            board_id=board.id if board else None,
            created_by_id=current_user.id,
        )
        self.session.add(channel)
        await self.session.flush()
        for member in members:
            self.session.add(
                ChatChannelMember(
                    channel_id=channel.id,
                    user_id=member.id,
                    role="owner" if member.id == current_user.id else "member",
                )
            )
        await self.session.commit()
        channel = await self._get_channel(channel.id)
        return ChatChannelResponse.from_model(channel, member_count=len(members))

    async def list_messages(
        self,
        channel_id: str,
        current_user: User,
        *,
        limit: int = 50,
        before_id: str | None = None,
        after_id: str | None = None,
        query: str | None = None,
    ) -> ChatMessagePageResponse:
        channel = await self._get_accessible_channel(channel_id, current_user)
        messages = await self._load_messages(
            channel,
            limit=limit,
            before_id=before_id,
            after_id=after_id,
            query=query,
        )
        has_more = len(messages) > limit
        page_messages = messages[:limit] if after_id else (messages[1:] if has_more else messages)
        return ChatMessagePageResponse(
            messages=[ChatMessageResponse.from_model(message) for message in page_messages],
            next_before_id=page_messages[0].id if has_more and page_messages else None,
            has_more=has_more,
        )

    async def send_message(
        self,
        channel_id: str,
        payload: ChatMessageCreateRequest,
        current_user: User,
    ) -> ChatMessageResponse:
        channel = await self._get_accessible_channel(channel_id, current_user)
        raw_text = payload.raw_text.strip()
        if not raw_text:
            raise ValidationError("chat_message_empty", "Chat message cannot be empty.")
        message = ChatMessage(channel_id=channel.id, user_id=current_user.id, raw_text=raw_text)
        self.session.add(message)
        await self.session.flush()
        channel.message_count += 1
        channel.last_message_at = message.created_at
        await self._touch_presence(channel.id, current_user, ChatPresenceUpdateRequest())
        await self.session.commit()
        message = await self._get_message(message.id)
        return ChatMessageResponse.from_model(message)

    async def update_presence(
        self,
        channel_id: str,
        payload: ChatPresenceUpdateRequest,
        current_user: User,
    ) -> ChatPresenceResponse:
        channel = await self._get_accessible_channel(channel_id, current_user)
        presence = await self._touch_presence(channel.id, current_user, payload)
        await self.session.commit()
        now = utcnow()
        return ChatPresenceResponse.from_model(
            presence,
            now=now,
            online_cutoff=now - timedelta(seconds=PRESENCE_TTL_SECONDS),
        )

    async def list_presence(
        self,
        channel_id: str,
        current_user: User,
    ) -> list[ChatPresenceResponse]:
        channel = await self._get_accessible_channel(channel_id, current_user)
        now = utcnow()
        online_cutoff = now - timedelta(seconds=PRESENCE_TTL_SECONDS)
        presence = list(
            await self.session.scalars(
                select(ChatPresence)
                .options(selectinload(ChatPresence.user))
                .where(
                    ChatPresence.channel_id == channel.id,
                    ChatPresence.last_seen_at >= online_cutoff,
                )
                .order_by(ChatPresence.last_seen_at.desc())
            )
        )
        return [
            ChatPresenceResponse.from_model(item, now=now, online_cutoff=online_cutoff)
            for item in presence
        ]

    async def stream_snapshot(
        self,
        channel_id: str,
        current_user: User,
        *,
        after_id: str | None,
        limit: int,
    ) -> ChatStreamResponse:
        channel = await self._get_accessible_channel(channel_id, current_user)
        messages = await self._load_messages(channel, limit=limit, after_id=after_id)
        return ChatStreamResponse(
            messages=[ChatMessageResponse.from_model(message) for message in messages[:limit]],
            presence=await self.list_presence(channel.id, current_user),
        )

    async def _get_channel(self, channel_id: str) -> ChatChannel:
        channel = await self.session.scalar(
            select(ChatChannel)
            .options(selectinload(ChatChannel.board))
            .where(ChatChannel.id == channel_id)
        )
        if channel is None:
            raise NotFoundError("chat_channel_not_found", "Chat channel not found")
        return channel

    async def _get_accessible_channel(self, channel_id: str, current_user: User) -> ChatChannel:
        channel = await self._get_channel(channel_id)
        if not await self._can_access_channel(channel, current_user):
            raise NotFoundError("chat_channel_not_found", "Chat channel not found")
        return channel

    async def _get_message(self, message_id: str) -> ChatMessage:
        message = await self.session.scalar(
            select(ChatMessage)
            .options(selectinload(ChatMessage.user))
            .where(ChatMessage.id == message_id)
        )
        if message is None:
            raise NotFoundError("chat_message_not_found", "Chat message not found")
        return message

    async def _get_board(self, board_slug: str) -> Board:
        board = await self.session.scalar(select(Board).where(Board.slug == board_slug))
        if board is None:
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def _can_access_channel(self, channel: ChatChannel, current_user: User) -> bool:
        if channel.channel_type == "public":
            return True
        if channel.channel_type == "board":
            return channel.board is not None and await self._can_access_board(
                channel.board,
                current_user,
            )
        return await self._is_channel_member(channel.id, current_user.id)

    async def _can_access_board(self, board: Board, current_user: User) -> bool:
        if board.visibility == "public" or board.owner_id == current_user.id:
            return True
        member_id = await self.session.scalar(
            select(BoardMember.id).where(
                BoardMember.board_id == board.id,
                BoardMember.user_id == current_user.id,
            )
        )
        return member_id is not None

    async def _is_channel_member(self, channel_id: str, user_id: str) -> bool:
        member_id = await self.session.scalar(
            select(ChatChannelMember.id).where(
                ChatChannelMember.channel_id == channel_id,
                ChatChannelMember.user_id == user_id,
            )
        )
        return member_id is not None

    async def _load_messages(
        self,
        channel: ChatChannel,
        *,
        limit: int,
        before_id: str | None = None,
        after_id: str | None = None,
        query: str | None = None,
    ) -> list[ChatMessage]:
        statement = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.user))
            .where(ChatMessage.channel_id == channel.id, ChatMessage.deleted_at.is_(None))
        )
        if before_id:
            anchor = await self._get_message_anchor(before_id, channel.id)
            statement = statement.where(ChatMessage.created_at < anchor.created_at)
        if after_id:
            anchor = await self._get_message_anchor(after_id, channel.id)
            statement = statement.where(ChatMessage.created_at > anchor.created_at)
        if query:
            statement = statement.where(ChatMessage.raw_text.ilike(f"%{escape_like(query)}%"))
        if after_id:
            statement = statement.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        else:
            statement = statement.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        messages = list(await self.session.scalars(statement.limit(limit + 1)))
        if after_id:
            return messages
        return list(reversed(messages))

    async def _get_message_anchor(self, message_id: str, channel_id: str) -> ChatMessage:
        message = await self.session.scalar(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.channel_id == channel_id,
            )
        )
        if message is None:
            raise NotFoundError("chat_message_not_found", "Chat message not found")
        return message

    async def _touch_presence(
        self,
        channel_id: str,
        current_user: User,
        payload: ChatPresenceUpdateRequest,
    ) -> ChatPresence:
        now = utcnow()
        presence = await self.session.scalar(
            select(ChatPresence).where(
                ChatPresence.channel_id == channel_id,
                ChatPresence.user_id == current_user.id,
            )
        )
        if presence is None:
            presence = ChatPresence(
                channel_id=channel_id,
                user_id=current_user.id,
                status=payload.status,
                last_seen_at=now,
            )
            self.session.add(presence)
        presence.status = payload.status
        presence.last_seen_at = now
        presence.typing_until = (
            now + timedelta(seconds=TYPING_TTL_SECONDS) if payload.typing else None
        )
        await self.session.flush()
        await self.session.refresh(presence, attribute_names=["user"])
        return presence

    async def _resolve_direct_recipients(
        self,
        usernames: list[str],
        current_user: User,
    ) -> list[User]:
        normalized: list[str] = []
        for username in usernames:
            stripped = username.strip()
            if stripped and stripped != current_user.username and stripped not in normalized:
                normalized.append(stripped)
        if not normalized:
            raise ValidationError(
                "chat_direct_participant_required",
                "At least one other participant is required.",
            )
        users = list(
            await self.session.scalars(
                select(User).where(User.username.in_(normalized), User.status == "active")
            )
        )
        found = {user.username for user in users}
        missing = [username for username in normalized if username not in found]
        if missing:
            raise NotFoundError("user_not_found", "User not found")
        return users

    async def _ensure_direct_allowed(self, current_user: User, recipients: list[User]) -> None:
        for recipient in recipients:
            if await self._has_block_boundary(current_user.id, recipient.id):
                raise ValidationError(
                    "chat_direct_blocked",
                    "Direct chat cannot cross a block boundary.",
                    {"username": recipient.username},
                )

    async def _has_block_boundary(self, first_user_id: str, second_user_id: str) -> bool:
        relationship_id = await self.session.scalar(
            select(UserRelationship.id).where(
                UserRelationship.relationship_type == "block",
                or_(
                    (
                        (UserRelationship.actor_user_id == first_user_id)
                        & (UserRelationship.target_user_id == second_user_id)
                    ),
                    (
                        (UserRelationship.actor_user_id == second_user_id)
                        & (UserRelationship.target_user_id == first_user_id)
                    ),
                ),
            )
        )
        return relationship_id is not None

    async def _unique_channel_slug(self, value: str) -> str:
        base_slug = slugify(value, fallback_prefix="chat")[:80]
        slug = base_slug
        attempt = 1
        while await self.session.scalar(select(ChatChannel.id).where(ChatChannel.slug == slug)):
            attempt += 1
            slug = f"{base_slug}-{attempt}"
        return slug

    async def _member_counts(self, channel_ids: list[str]) -> dict[str, int]:
        if not channel_ids:
            return {}
        rows = await self.session.execute(
            select(ChatChannelMember.channel_id, func.count(ChatChannelMember.id))
            .where(ChatChannelMember.channel_id.in_(channel_ids))
            .group_by(ChatChannelMember.channel_id)
        )
        return {str(channel_id): int(count) for channel_id, count in rows}
