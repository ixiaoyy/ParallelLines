from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import utcnow
from app.models.forum import Board, BoardMember, NotificationLevel, Post, Topic, TopicRead
from app.models.interaction import Bookmark, Notification, Reaction, Vote
from app.models.social import UserRelationship
from app.models.user import User
from app.schemas.interactions import (
    BoardFollowResponse,
    InteractionStateResponse,
    NotificationReadResponse,
    NotificationResponse,
    NotificationStreamResponse,
    VoteStateResponse,
)
from app.services.background_jobs import BackgroundJobService
from app.services.badges import BadgeTrustService
from app.services.forum import calculate_hot_score, notification_idempotency_key
from app.services.growth import GrowthService


class InteractionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def follow_board(
        self,
        slug: str,
        current_user: User,
        *,
        notification_level: NotificationLevel | None = None,
    ) -> BoardFollowResponse:
        board = await self._get_board(slug, current_user)
        next_notification_level = notification_level or board.default_notification_level
        member = await self._get_board_member(board.id, current_user.id)
        if member:
            member.notification_level = next_notification_level
        else:
            member = BoardMember(
                board_id=board.id,
                user_id=current_user.id,
                role="follower",
                notification_level=next_notification_level,
            )
            self.session.add(member)
            board.follower_count += 1

        await self.session.commit()
        return BoardFollowResponse(
            board_id=board.id,
            board_slug=board.slug,
            following=True,
            role=member.role,
            notification_level=member.notification_level,
            follower_count=board.follower_count,
        )

    async def unfollow_board(self, slug: str, current_user: User) -> BoardFollowResponse:
        board = await self._get_board(slug, current_user)
        member = await self._get_board_member(board.id, current_user.id)
        if not member:
            return BoardFollowResponse(
                board_id=board.id,
                board_slug=board.slug,
                following=False,
                role=None,
                notification_level=None,
                follower_count=board.follower_count,
            )
        if member.role == "owner":
            raise ValidationError("board_owner_cannot_unfollow", "Board owner cannot unfollow")

        await self.session.delete(member)
        board.follower_count = max(0, board.follower_count - 1)
        await self.session.commit()
        return BoardFollowResponse(
            board_id=board.id,
            board_slug=board.slug,
            following=False,
            role=None,
            notification_level=None,
            follower_count=board.follower_count,
        )

    async def like_post(self, post_id: str, current_user: User) -> InteractionStateResponse:
        post = await self._get_post(post_id, current_user)
        existing = await self._get_reaction("post", post.id, current_user.id)
        if not existing:
            self.session.add(
                Reaction(
                    target_type="post",
                    target_id=post.id,
                    user_id=current_user.id,
                    type="like",
                )
            )
            post.like_count += 1
            post.topic.like_count += 1
            post.topic.hot_score = calculate_hot_score(
                reply_count=post.topic.reply_count,
                like_count=post.topic.like_count,
                view_count=post.topic.view_count,
            )
            await self._enqueue_like_notification(
                recipient_id=post.user_id,
                topic=post.topic,
                post=post,
                current_user=current_user,
            )
            if post.user_id != current_user.id:
                await GrowthService(self.session).award(
                    post.user_id,
                    "content_liked",
                    source_id=post.id,
                    actor_id=current_user.id,
                    note="帖子被点赞奖励",
                    idempotency_key=f"content_liked:post:{post.id}:{current_user.id}",
                )
                owner = await self.session.get(User, post.user_id)
                if owner is not None:
                    badge_service = BadgeTrustService(self.session)
                    await badge_service.grant_badge(
                        user_id=owner.id,
                        badge_slug="received-like",
                        source_type="content_liked",
                        source_id=post.id,
                        actor_id=current_user.id,
                        note="帖子第一次收到认可",
                        idempotency_key=f"badge:received-like:{owner.id}",
                    )
                    await badge_service.recompute_trust(
                        owner,
                        source_type="content_liked",
                        source_id=post.id,
                        actor_id=current_user.id,
                        note="内容获赞后重算信任等级",
                    )
        await self.session.flush()
        count = await self._reaction_count("post", post.id)
        await self.session.commit()
        return InteractionStateResponse(
            target_type="post",
            target_id=post.id,
            active=True,
            count=count,
        )

    async def unlike_post(self, post_id: str, current_user: User) -> InteractionStateResponse:
        post = await self._get_post(post_id, current_user)
        existing = await self._get_reaction("post", post.id, current_user.id)
        if existing:
            await self.session.delete(existing)
            post.like_count = max(0, post.like_count - 1)
            post.topic.like_count = max(0, post.topic.like_count - 1)
            post.topic.hot_score = calculate_hot_score(
                reply_count=post.topic.reply_count,
                like_count=post.topic.like_count,
                view_count=post.topic.view_count,
            )
        await self.session.flush()
        count = await self._reaction_count("post", post.id)
        await self.session.commit()
        return InteractionStateResponse(
            target_type="post",
            target_id=post.id,
            active=False,
            count=count,
        )

    async def like_topic(self, topic_id: str, current_user: User) -> InteractionStateResponse:
        topic = await self._get_topic(topic_id, current_user)
        existing = await self._get_reaction("topic", topic.id, current_user.id)
        if not existing:
            self.session.add(
                Reaction(
                    target_type="topic",
                    target_id=topic.id,
                    user_id=current_user.id,
                    type="like",
                )
            )
            topic.like_count += 1
            topic.hot_score = calculate_hot_score(
                reply_count=topic.reply_count,
                like_count=topic.like_count,
                view_count=topic.view_count,
            )
            await self._enqueue_like_notification(
                recipient_id=topic.user_id,
                topic=topic,
                post=None,
                current_user=current_user,
            )
            if topic.user_id != current_user.id:
                await GrowthService(self.session).award(
                    topic.user_id,
                    "content_liked",
                    source_id=topic.id,
                    actor_id=current_user.id,
                    note="主题被点赞奖励",
                    idempotency_key=f"content_liked:topic:{topic.id}:{current_user.id}",
                )
                owner = await self.session.get(User, topic.user_id)
                if owner is not None:
                    badge_service = BadgeTrustService(self.session)
                    await badge_service.grant_badge(
                        user_id=owner.id,
                        badge_slug="received-like",
                        source_type="content_liked",
                        source_id=topic.id,
                        actor_id=current_user.id,
                        note="主题第一次收到认可",
                        idempotency_key=f"badge:received-like:{owner.id}",
                    )
                    await badge_service.recompute_trust(
                        owner,
                        source_type="content_liked",
                        source_id=topic.id,
                        actor_id=current_user.id,
                        note="内容获赞后重算信任等级",
                    )
        await self.session.flush()
        await self.session.commit()
        return InteractionStateResponse(
            target_type="topic",
            target_id=topic.id,
            active=True,
            count=topic.like_count,
        )

    async def unlike_topic(self, topic_id: str, current_user: User) -> InteractionStateResponse:
        topic = await self._get_topic(topic_id, current_user)
        existing = await self._get_reaction("topic", topic.id, current_user.id)
        if existing:
            await self.session.delete(existing)
            topic.like_count = max(0, topic.like_count - 1)
            topic.hot_score = calculate_hot_score(
                reply_count=topic.reply_count,
                like_count=topic.like_count,
                view_count=topic.view_count,
            )
        await self.session.flush()
        await self.session.commit()
        return InteractionStateResponse(
            target_type="topic",
            target_id=topic.id,
            active=False,
            count=topic.like_count,
        )

    async def bookmark_topic(self, topic_id: str, current_user: User) -> InteractionStateResponse:
        topic = await self._get_topic(topic_id, current_user)
        existing = await self._get_bookmark("topic", topic.id, current_user.id)
        if not existing:
            self.session.add(
                Bookmark(target_type="topic", target_id=topic.id, user_id=current_user.id)
            )
            if topic.user_id != current_user.id:
                await GrowthService(self.session).award(
                    topic.user_id,
                    "content_bookmarked",
                    source_id=topic.id,
                    actor_id=current_user.id,
                    note="主题被收藏奖励",
                    idempotency_key=f"content_bookmarked:topic:{topic.id}:{current_user.id}",
                )
        await self.session.flush()
        count = await self._bookmark_count("topic", topic.id)
        await self.session.commit()
        return InteractionStateResponse(
            target_type="topic",
            target_id=topic.id,
            active=True,
            count=count,
        )

    async def unbookmark_topic(self, topic_id: str, current_user: User) -> InteractionStateResponse:
        topic = await self._get_topic(topic_id, current_user)
        existing = await self._get_bookmark("topic", topic.id, current_user.id)
        if existing:
            await self.session.delete(existing)
        await self.session.flush()
        count = await self._bookmark_count("topic", topic.id)
        await self.session.commit()
        return InteractionStateResponse(
            target_type="topic",
            target_id=topic.id,
            active=False,
            count=count,
        )


    async def vote_topic(
        self,
        topic_id: str,
        value: int,
        current_user: User,
    ) -> VoteStateResponse:
        topic = await self._get_topic(topic_id, current_user)
        return await self._set_vote(
            target_type="topic",
            target_id=topic.id,
            current_value=value,
            current_user=current_user,
            score_owner=topic,
        )

    async def vote_post(
        self,
        post_id: str,
        value: int,
        current_user: User,
    ) -> VoteStateResponse:
        post = await self._get_post(post_id, current_user)
        return await self._set_vote(
            target_type="post",
            target_id=post.id,
            current_value=value,
            current_user=current_user,
            score_owner=post,
        )

    async def list_notifications(
        self,
        current_user: User,
        *,
        unread_only: bool = False,
        limit: int = 30,
    ) -> tuple[list[Notification], int]:
        statement = (
            select(Notification)
            .options(selectinload(Notification.actor))
            .where(Notification.user_id == current_user.id)
            .order_by(desc(Notification.created_at))
            .limit(limit)
        )
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        notifications = list(await self.session.scalars(statement))
        unread_count = await self.unread_notification_count(current_user)
        return notifications, unread_count

    async def mark_notifications_read(
        self,
        current_user: User,
        *,
        ids: list[str] | None = None,
    ) -> NotificationReadResponse:
        statement = select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
        if ids:
            statement = statement.where(Notification.id.in_(ids))
        notifications = list(await self.session.scalars(statement))
        now = utcnow()
        for notification in notifications:
            notification.read_at = now
        await self.session.commit()
        unread_count = await self.unread_notification_count(current_user)
        return NotificationReadResponse(
            updated_count=len(notifications),
            unread_count=unread_count,
        )

    async def unread_notification_count(self, current_user: User) -> int:
        count = await self.session.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id,
                Notification.read_at.is_(None),
            )
        )
        return count or 0

    async def notification_stream_snapshot(
        self,
        current_user: User,
        *,
        limit: int = 5,
    ) -> NotificationStreamResponse:
        notifications, unread_count = await self.list_notifications(
            current_user,
            unread_only=True,
            limit=limit,
        )
        return NotificationStreamResponse(
            unread_count=unread_count,
            notifications=[
                NotificationResponse.from_model(notification) for notification in notifications
            ],
        )

    async def _set_vote(
        self,
        *,
        target_type: str,
        target_id: str,
        current_value: int,
        current_user: User,
        score_owner: Topic | Post,
    ) -> VoteStateResponse:
        existing = await self._get_vote(target_type, target_id, current_user.id)
        previous_value = existing.value if existing else 0
        next_value = current_value
        if next_value == 0:
            if existing:
                await self.session.delete(existing)
                score_owner.vote_count = max(0, score_owner.vote_count - 1)
        elif existing:
            existing.value = next_value
        else:
            self.session.add(
                Vote(
                    target_type=target_type,
                    target_id=target_id,
                    user_id=current_user.id,
                    value=next_value,
                )
            )
            score_owner.vote_count += 1
        if previous_value != next_value:
            score_owner.vote_score += next_value - previous_value
            if isinstance(score_owner, Topic):
                score_owner.hot_score = calculate_hot_score(
                    reply_count=score_owner.reply_count,
                    like_count=score_owner.like_count,
                    view_count=score_owner.view_count,
                )
        await self.session.flush()
        count = await self._vote_count(target_type, target_id)
        score = await self._vote_score(target_type, target_id)
        score_owner.vote_count = count
        score_owner.vote_score = score
        await self.session.commit()
        return VoteStateResponse(
            target_type=target_type,
            target_id=target_id,
            value=next_value,
            score=score,
            count=count,
        )

    async def _relationship_blocks_notification(self, recipient_id: str, actor_id: str) -> bool:
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

    async def _enqueue_like_notification(
        self,
        *,
        recipient_id: str,
        topic: Topic,
        post: Post | None,
        current_user: User,
    ) -> None:
        if recipient_id == current_user.id:
            return
        recipient_read_state = await self.session.scalar(
            select(TopicRead).where(
                TopicRead.topic_id == topic.id,
                TopicRead.user_id == recipient_id,
            )
        )
        if recipient_read_state and recipient_read_state.notification_level == "muted":
            return
        if await self._relationship_blocks_notification(
            recipient_id=recipient_id,
            actor_id=current_user.id,
        ):
            return

        notification_data: dict[str, object] = {
            "topic_title": topic.title,
            "topic_slug": topic.slug,
            "actor_name": current_user.username,
        }
        post_id = None
        if post is not None:
            post_id = post.id
            notification_data["post_number"] = post.post_number

        await BackgroundJobService(self.session).enqueue_notification(
            user_id=recipient_id,
            kind="liked",
            topic_id=topic.id,
            post_id=post_id,
            actor_id=current_user.id,
            data=notification_data,
            idempotency_key=notification_idempotency_key(
                kind="liked",
                user_id=recipient_id,
                topic_id=topic.id,
                post_id=post_id,
                actor_id=current_user.id,
                data=notification_data,
            ),
            commit=False,
        )

    async def _get_board(self, slug: str, current_user: User) -> Board:
        board = await self.session.scalar(select(Board).where(Board.slug == slug))
        if not board or not await self._can_access_board(board, current_user):
            raise NotFoundError("board_not_found", "Board not found")
        return board

    async def _get_topic(self, topic_id: str, current_user: User) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .options(selectinload(Topic.board))
            .where(Topic.id == topic_id, Topic.deleted_at.is_(None))
        )
        if not topic or not await self._can_access_board(topic.board, current_user):
            raise NotFoundError("topic_not_found", "Topic not found")
        return topic

    async def _get_post(self, post_id: str, current_user: User) -> Post:
        post = await self.session.scalar(
            select(Post)
            .options(selectinload(Post.topic).selectinload(Topic.board))
            .where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        if not post or not await self._can_access_board(post.topic.board, current_user):
            raise NotFoundError("post_not_found", "Post not found")
        return post

    async def _can_access_board(self, board: Board, current_user: User) -> bool:
        if board.visibility == "public":
            return True
        if board.owner_id == current_user.id:
            return True
        member = await self._get_board_member(board.id, current_user.id)
        return member is not None


    async def _get_vote(self, target_type: str, target_id: str, user_id: str) -> Vote | None:
        return await self.session.scalar(
            select(Vote).where(
                Vote.target_type == target_type,
                Vote.target_id == target_id,
                Vote.user_id == user_id,
            )
        )

    async def _vote_count(self, target_type: str, target_id: str) -> int:
        count = await self.session.scalar(
            select(func.count(Vote.id)).where(
                Vote.target_type == target_type,
                Vote.target_id == target_id,
            )
        )
        return count or 0

    async def _vote_score(self, target_type: str, target_id: str) -> int:
        score = await self.session.scalar(
            select(func.coalesce(func.sum(Vote.value), 0)).where(
                Vote.target_type == target_type,
                Vote.target_id == target_id,
            )
        )
        return int(score or 0)

    async def _get_board_member(self, board_id: str, user_id: str) -> BoardMember | None:
        return await self.session.scalar(
            select(BoardMember).where(
                BoardMember.board_id == board_id,
                BoardMember.user_id == user_id,
            )
        )

    async def _get_reaction(
        self,
        target_type: str,
        target_id: str,
        user_id: str,
    ) -> Reaction | None:
        return await self.session.scalar(
            select(Reaction).where(
                Reaction.target_type == target_type,
                Reaction.target_id == target_id,
                Reaction.user_id == user_id,
                Reaction.type == "like",
            )
        )

    async def _reaction_count(self, target_type: str, target_id: str) -> int:
        count = await self.session.scalar(
            select(func.count(Reaction.id)).where(
                Reaction.target_type == target_type,
                Reaction.target_id == target_id,
                Reaction.type == "like",
            )
        )
        return count or 0

    async def _get_bookmark(
        self,
        target_type: str,
        target_id: str,
        user_id: str,
    ) -> Bookmark | None:
        return await self.session.scalar(
            select(Bookmark).where(
                Bookmark.target_type == target_type,
                Bookmark.target_id == target_id,
                Bookmark.user_id == user_id,
            )
        )

    async def _bookmark_count(self, target_type: str, target_id: str) -> int:
        count = await self.session.scalar(
            select(func.count(Bookmark.id)).where(
                and_(Bookmark.target_type == target_type, Bookmark.target_id == target_id)
            )
        )
        return count or 0
