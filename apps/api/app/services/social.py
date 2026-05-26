from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import utcnow
from app.models.forum import Board, Post, Topic
from app.models.social import PrivateMessageParticipant, UserRelationship, UserRelationshipType
from app.models.user import User
from app.schemas.users import (
    PrivateMessageCreateRequest,
    PrivateMessageTopicResponse,
    UserRelationshipStateResponse,
)
from app.services.background_jobs import BackgroundJobService
from app.services.forum import (
    calculate_hot_score,
    notification_idempotency_key,
    render_markdown,
    slugify,
)

PRIVATE_MESSAGE_BOARD_SLUG = "private-messages"


class SocialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def relationship_state(
        self,
        username: str,
        current_user: User,
    ) -> UserRelationshipStateResponse:
        target = await self._get_target_user(username)
        relationships = await self._relationship_types(current_user.id, target.id)
        reverse_relationships = await self._relationship_types(target.id, current_user.id)
        return UserRelationshipStateResponse(
            target_user_id=target.id,
            target_username=target.username,
            following="follow" in relationships,
            ignored="ignore" in relationships,
            blocked="block" in relationships,
            followed_by="follow" in reverse_relationships,
        )

    async def set_relationship(
        self,
        username: str,
        relationship_type: UserRelationshipType,
        current_user: User,
    ) -> UserRelationshipStateResponse:
        target = await self._get_target_user(username)
        self._ensure_not_self(target, current_user)
        if relationship_type == "follow" and await self._has_block_boundary(
            current_user.id,
            target.id,
        ):
            raise ValidationError(
                "relationship_blocked",
                "Cannot follow a user across a block boundary.",
            )

        existing = await self._get_relationship(current_user.id, target.id, relationship_type)
        if existing is None:
            self.session.add(
                UserRelationship(
                    actor_user_id=current_user.id,
                    target_user_id=target.id,
                    relationship_type=relationship_type,
                )
            )

        if relationship_type in {"ignore", "block"}:
            await self.session.execute(
                delete(UserRelationship).where(
                    UserRelationship.actor_user_id == current_user.id,
                    UserRelationship.target_user_id == target.id,
                    UserRelationship.relationship_type == "follow",
                )
            )
        if relationship_type == "block":
            await self.session.execute(
                delete(UserRelationship).where(
                    UserRelationship.actor_user_id == target.id,
                    UserRelationship.target_user_id == current_user.id,
                    UserRelationship.relationship_type == "follow",
                )
            )

        await self.session.commit()
        return await self.relationship_state(username, current_user)

    async def clear_relationship(
        self,
        username: str,
        relationship_type: UserRelationshipType,
        current_user: User,
    ) -> UserRelationshipStateResponse:
        target = await self._get_target_user(username)
        await self.session.execute(
            delete(UserRelationship).where(
                UserRelationship.actor_user_id == current_user.id,
                UserRelationship.target_user_id == target.id,
                UserRelationship.relationship_type == relationship_type,
            )
        )
        await self.session.commit()
        return await self.relationship_state(username, current_user)

    async def list_private_messages(
        self,
        current_user: User,
        *,
        limit: int = 30,
    ) -> list[PrivateMessageTopicResponse]:
        topics = list(
            await self.session.scalars(
                select(Topic)
                .join(PrivateMessageParticipant)
                .options(
                    selectinload(Topic.board),
                    selectinload(Topic.author),
                    selectinload(Topic.tags),
                    selectinload(Topic.posts),
                )
                .where(
                    Topic.visibility == "private_message",
                    Topic.deleted_at.is_(None),
                    PrivateMessageParticipant.user_id == current_user.id,
                )
                .order_by(desc(Topic.last_posted_at))
                .limit(limit)
            )
        )
        if not topics:
            return []
        participants_by_topic = await self._participants_by_topic([topic.id for topic in topics])
        return [
            PrivateMessageTopicResponse.from_topic(
                topic,
                participants_by_topic.get(topic.id, []),
                current_user_id=current_user.id,
            )
            for topic in topics
        ]

    async def create_private_message(
        self,
        payload: PrivateMessageCreateRequest,
        current_user: User,
    ) -> PrivateMessageTopicResponse:
        recipients = await self._resolve_message_recipients(
            payload.participant_usernames,
            current_user,
        )
        await self._ensure_message_allowed(current_user, recipients)
        board = await self._ensure_private_message_board()
        title = payload.title.strip()
        raw_md = payload.raw_md.strip()
        if not raw_md:
            raise ValidationError("empty_post", "Post content cannot be empty")
        now = utcnow()
        topic = Topic(
            board_id=board.id,
            user_id=current_user.id,
            title=title,
            slug=await self._unique_private_message_slug(board.id, title),
            topic_type="private_message",
            visibility="private_message",
            hot_score=calculate_hot_score(reply_count=0, like_count=0, view_count=0),
            last_posted_at=now,
            tags=[],
        )
        self.session.add(topic)
        await self.session.flush()

        post = Post(
            topic_id=topic.id,
            user_id=current_user.id,
            post_number=1,
            raw_md=raw_md,
            cooked_html=render_markdown(raw_md),
        )
        self.session.add(post)
        board.topic_count += 1
        board.post_count += 1
        all_participants = [current_user, *recipients]
        for user in all_participants:
            self.session.add(
                PrivateMessageParticipant(
                    topic_id=topic.id,
                    user_id=user.id,
                    role="owner" if user.id == current_user.id else "participant",
                    last_read_post_number=1 if user.id == current_user.id else 0,
                    last_read_at=now if user.id == current_user.id else None,
                )
            )
        await self.session.flush()

        for recipient in recipients:
            await self._enqueue_private_message_notification(recipient, topic, post, current_user)

        await self.session.commit()
        topic = await self._get_private_message_topic(topic.id)
        participants = (await self._participants_by_topic([topic.id]))[topic.id]
        return PrivateMessageTopicResponse.from_topic(
            topic,
            participants,
            current_user_id=current_user.id,
        )

    async def _get_target_user(self, username: str) -> User:
        user = await self.session.scalar(select(User).where(User.username == username))
        if user is None:
            raise NotFoundError("user_not_found", "User not found")
        return user

    def _ensure_not_self(self, target: User, current_user: User) -> None:
        if target.id == current_user.id:
            raise ValidationError("relationship_self_not_allowed", "Cannot relate to yourself")

    async def _relationship_types(self, actor_user_id: str, target_user_id: str) -> set[str]:
        result = await self.session.scalars(
            select(UserRelationship.relationship_type).where(
                UserRelationship.actor_user_id == actor_user_id,
                UserRelationship.target_user_id == target_user_id,
            )
        )
        return set(result)

    async def _get_relationship(
        self,
        actor_user_id: str,
        target_user_id: str,
        relationship_type: UserRelationshipType,
    ) -> UserRelationship | None:
        return await self.session.scalar(
            select(UserRelationship).where(
                UserRelationship.actor_user_id == actor_user_id,
                UserRelationship.target_user_id == target_user_id,
                UserRelationship.relationship_type == relationship_type,
            )
        )

    async def _has_block_boundary(self, first_user_id: str, second_user_id: str) -> bool:
        relationship = await self.session.scalar(
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
        return relationship is not None

    async def _resolve_message_recipients(
        self,
        usernames: Iterable[str],
        current_user: User,
    ) -> list[User]:
        normalized = []
        for username in usernames:
            stripped = username.strip()
            if stripped and stripped != current_user.username and stripped not in normalized:
                normalized.append(stripped)
        if not normalized:
            raise ValidationError(
                "private_message_participant_required",
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

    async def _ensure_message_allowed(self, current_user: User, recipients: list[User]) -> None:
        for recipient in recipients:
            if await self._has_block_boundary(current_user.id, recipient.id):
                raise ValidationError(
                    "private_message_blocked",
                    "Private messages cannot cross a block boundary.",
                    {"username": recipient.username},
                )

    async def _ensure_private_message_board(self) -> Board:
        board = await self.session.scalar(
            select(Board).where(Board.slug == PRIVATE_MESSAGE_BOARD_SLUG)
        )
        if board is not None:
            return board
        board = Board(
            slug=PRIVATE_MESSAGE_BOARD_SLUG,
            name="私信",
            description="系统私信主题容器，不在公开版块列表展示。",
            color="#409EFF",
            owner_id=None,
            visibility="private",
            topic_count=0,
            post_count=0,
            follower_count=0,
        )
        self.session.add(board)
        await self.session.flush()
        return board

    async def _unique_private_message_slug(self, board_id: str, title: str) -> str:
        base_slug = slugify(title, fallback_prefix="pm")[:180]
        slug = base_slug
        attempt = 1
        while await self.session.scalar(
            select(Topic.id).where(Topic.board_id == board_id, Topic.slug == slug)
        ):
            attempt += 1
            slug = f"{base_slug}-{attempt}"
        return slug

    async def _get_private_message_topic(self, topic_id: str) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(
                selectinload(Topic.board),
                selectinload(Topic.author),
                selectinload(Topic.tags),
                selectinload(Topic.posts),
            )
            .where(Topic.id == topic_id, Topic.visibility == "private_message")
        )
        if topic is None:
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def _participants_by_topic(
        self,
        topic_ids: list[str],
    ) -> dict[str, list[PrivateMessageParticipant]]:
        participants = list(
            await self.session.scalars(
                select(PrivateMessageParticipant)
                .options(selectinload(PrivateMessageParticipant.user))
                .where(PrivateMessageParticipant.topic_id.in_(topic_ids))
                .order_by(
                    PrivateMessageParticipant.role.desc(),
                    PrivateMessageParticipant.joined_at,
                )
            )
        )
        grouped: dict[str, list[PrivateMessageParticipant]] = {}
        for participant in participants:
            grouped.setdefault(participant.topic_id, []).append(participant)
        return grouped

    async def _enqueue_private_message_notification(
        self,
        recipient: User,
        topic: Topic,
        post: Post,
        current_user: User,
    ) -> None:
        if await self._relationship_suppresses_notification(recipient.id, current_user.id):
            return
        data = {
            "topic_title": topic.title,
            "topic_slug": topic.slug,
            "post_number": post.post_number,
            "actor_name": current_user.username,
        }
        await BackgroundJobService(self.session).enqueue_notification(
            user_id=recipient.id,
            kind="private_message",
            topic_id=topic.id,
            post_id=post.id,
            actor_id=current_user.id,
            data=data,
            idempotency_key=notification_idempotency_key(
                kind="private_message",
                user_id=recipient.id,
                topic_id=topic.id,
                post_id=post.id,
                actor_id=current_user.id,
                data=data,
            ),
            commit=False,
        )

    async def _relationship_suppresses_notification(
        self,
        recipient_id: str,
        actor_id: str,
    ) -> bool:
        relationship_id = await self.session.scalar(
            select(UserRelationship.id).where(
                (
                    (UserRelationship.actor_user_id == recipient_id)
                    & (UserRelationship.target_user_id == actor_id)
                    & (UserRelationship.relationship_type.in_(("ignore", "block")))
                )
                | (
                    (UserRelationship.actor_user_id == actor_id)
                    & (UserRelationship.target_user_id == recipient_id)
                    & (UserRelationship.relationship_type == "block")
                )
            )
        )
        return relationship_id is not None
