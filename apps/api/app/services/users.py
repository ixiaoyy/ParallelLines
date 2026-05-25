from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.models.forum import Board, Post, Topic
from app.models.interaction import Bookmark, Reaction
from app.models.user import User
from app.schemas.users import (
    UserActivityItemResponse,
    UserDirectoryResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)

URL_PATTERN = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class UserContentCounts:
    topic_count: int
    post_count: int


class UserProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(
        self,
        username: str,
        *,
        current_user: User | None = None,
    ) -> UserProfileResponse:
        user = await self._user_by_username(username)
        counts = await self._content_counts(user.id)
        return await self._profile_response(user, counts=counts, current_user=current_user)

    async def update_my_profile(
        self,
        payload: UserProfileUpdateRequest,
        current_user: User,
    ) -> UserProfileResponse:
        if "display_name" in payload.model_fields_set:
            current_user.display_name = self._clean_optional_text(
                payload.display_name,
                max_length=80,
            )
        if "bio" in payload.model_fields_set:
            current_user.bio = self._clean_optional_text(payload.bio, max_length=1000)
        if "website_url" in payload.model_fields_set:
            current_user.website_url = self._clean_url(payload.website_url)
        if "location" in payload.model_fields_set:
            current_user.location = self._clean_optional_text(payload.location, max_length=120)
        if payload.profile_visibility is not None:
            current_user.profile_visibility = payload.profile_visibility
        if payload.show_activity is not None:
            current_user.show_activity = payload.show_activity
        if payload.interface_theme is not None:
            current_user.interface_theme = payload.interface_theme
        if payload.locale is not None:
            current_user.locale = payload.locale

        await self.session.commit()
        await self.session.refresh(current_user)
        counts = await self._content_counts(current_user.id)
        return await self._profile_response(current_user, counts=counts, current_user=current_user)

    async def list_directory(self, *, sort: str, limit: int) -> list[UserDirectoryResponse]:
        topic_counts = (
            select(Topic.user_id.label("user_id"), func.count(Topic.id).label("topic_count"))
            .join(Topic.board)
            .where(*self._public_topic_conditions())
            .group_by(Topic.user_id)
            .subquery()
        )
        post_counts = (
            select(Post.user_id.label("user_id"), func.count(Post.id).label("post_count"))
            .join(Post.topic)
            .join(Topic.board)
            .where(Post.deleted_at.is_(None), *self._public_topic_conditions())
            .group_by(Post.user_id)
            .subquery()
        )
        statement = (
            select(
                User,
                func.coalesce(topic_counts.c.topic_count, 0).label("topic_count"),
                func.coalesce(post_counts.c.post_count, 0).label("post_count"),
            )
            .outerjoin(topic_counts, topic_counts.c.user_id == User.id)
            .outerjoin(post_counts, post_counts.c.user_id == User.id)
            .where(User.status == "active", User.profile_visibility != "private")
            .limit(limit)
        )
        if sort == "level":
            statement = statement.order_by(
                desc(User.level),
                desc(User.experience_total),
                User.username,
            )
        elif sort == "contribution":
            contribution = func.coalesce(topic_counts.c.topic_count, 0) + func.coalesce(
                post_counts.c.post_count,
                0,
            )
            statement = statement.order_by(
                desc(contribution),
                User.username,
            )
        else:
            statement = statement.order_by(
                desc(User.last_seen_at),
                desc(User.created_at),
                User.username,
            )

        rows = (await self.session.execute(statement)).all()
        return [
            UserDirectoryResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                role=user.role,
                level=user.level,
                trust_level=user.trust_level,
                trust_level_label=user.trust_level_label,
                points_balance=user.points_balance,
                topic_count=int(topic_count),
                post_count=int(post_count),
                last_seen_at=user.last_seen_at,
                created_at=user.created_at,
            )
            for user, topic_count, post_count in rows
        ]

    async def list_activity(
        self,
        username: str,
        *,
        current_user: User | None,
        activity_type: str,
        limit: int,
    ) -> list[UserActivityItemResponse]:
        user = await self._user_by_username(username)
        if not self._can_view_activity(user, current_user):
            raise PermissionDeniedError("profile_activity_private", "Profile activity is private")

        if activity_type == "likes":
            return await self._reaction_activity(user.id, limit)
        if activity_type == "bookmarks":
            return await self._bookmark_activity(user.id, limit)
        return await self._post_activity(user.id, limit)

    async def _profile_response(
        self,
        user: User,
        *,
        counts: UserContentCounts,
        current_user: User | None,
    ) -> UserProfileResponse:
        can_edit = current_user is not None and (
            current_user.id == user.id or is_admin(current_user)
        )
        can_view_private = self._can_view_private_profile(user, current_user)
        badges = []
        try:
            from app.services.badges import BadgeTrustService

            badges = await BadgeTrustService(self.session).list_user_badges(user.id)
        except Exception:
            badges = []
        return UserProfileResponse(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            display_name=user.display_name if can_view_private else None,
            bio=user.bio if can_view_private else None,
            website_url=user.website_url if can_view_private else None,
            location=user.location if can_view_private else None,
            role=user.role,
            level=user.level,
            trust_level=user.trust_level,
            trust_level_label=user.trust_level_label,
            points_balance=user.points_balance,
            experience_total=user.experience_total,
            experience_to_next_level=user.experience_to_next_level,
            level_progress_percent=user.level_progress_percent,
            status=user.status,
            profile_visibility=user.profile_visibility,
            show_activity=user.show_activity if can_view_private else False,
            can_edit=can_edit,
            created_at=user.created_at,
            topic_count=counts.topic_count,
            post_count=counts.post_count,
            badges=badges,
        )

    async def _content_counts(self, user_id: str) -> UserContentCounts:
        topic_count = int(
            await self.session.scalar(
                select(func.count(Topic.id))
                .join(Topic.board)
                .where(Topic.user_id == user_id, *self._public_topic_conditions())
            )
            or 0
        )
        post_count = int(
            await self.session.scalar(
                select(func.count(Post.id))
                .join(Post.topic)
                .join(Topic.board)
                .where(
                    Post.user_id == user_id,
                    Post.deleted_at.is_(None),
                    *self._public_topic_conditions(),
                )
            )
            or 0
        )
        return UserContentCounts(topic_count=topic_count, post_count=post_count)

    async def _post_activity(self, user_id: str, limit: int) -> list[UserActivityItemResponse]:
        posts = list(
            await self.session.scalars(
                select(Post)
                .join(Post.topic)
                .join(Topic.board)
                .options(selectinload(Post.topic))
                .where(
                    Post.user_id == user_id,
                    Post.deleted_at.is_(None),
                    *self._public_topic_conditions(),
                )
                .order_by(desc(Post.created_at))
                .limit(limit)
            )
        )
        return [
            UserActivityItemResponse(
                id=post.id,
                type="post",
                created_at=post.created_at,
                topic_id=post.topic_id,
                topic_title=post.topic.title,
                topic_slug=post.topic.slug,
                post_number=post.post_number,
                excerpt=self._excerpt(post.raw_md or post.cooked_html),
            )
            for post in posts
        ]

    async def _reaction_activity(self, user_id: str, limit: int) -> list[UserActivityItemResponse]:
        reactions = list(
            await self.session.scalars(
                select(Reaction)
                .where(Reaction.user_id == user_id, Reaction.type == "like")
                .order_by(desc(Reaction.created_at))
                .limit(limit)
            )
        )
        return await self._interaction_activity(reactions, "liked_topic", "liked_post")

    async def _bookmark_activity(self, user_id: str, limit: int) -> list[UserActivityItemResponse]:
        bookmarks = list(
            await self.session.scalars(
                select(Bookmark)
                .where(Bookmark.user_id == user_id)
                .order_by(desc(Bookmark.created_at))
                .limit(limit)
            )
        )
        return await self._interaction_activity(bookmarks, "bookmarked_topic", "bookmarked_post")

    async def _interaction_activity(
        self,
        rows: list[Reaction] | list[Bookmark],
        topic_type: str,
        post_type: str,
    ) -> list[UserActivityItemResponse]:
        items: list[UserActivityItemResponse] = []
        for row in rows:
            if row.target_type == "topic":
                topic = await self._public_topic(row.target_id)
                if topic is None:
                    continue
                items.append(
                    UserActivityItemResponse(
                        id=row.id,
                        type=topic_type,  # type: ignore[arg-type]
                        created_at=row.created_at,
                        topic_id=topic.id,
                        topic_title=topic.title,
                        topic_slug=topic.slug,
                        post_number=None,
                        excerpt="收藏/点赞了这个公开主题。",
                    )
                )
            elif row.target_type == "post":
                post = await self._public_post(row.target_id)
                if post is None:
                    continue
                items.append(
                    UserActivityItemResponse(
                        id=row.id,
                        type=post_type,  # type: ignore[arg-type]
                        created_at=row.created_at,
                        topic_id=post.topic_id,
                        topic_title=post.topic.title,
                        topic_slug=post.topic.slug,
                        post_number=post.post_number,
                        excerpt=self._excerpt(post.raw_md or post.cooked_html),
                    )
                )
        return items

    async def _public_topic(self, topic_id: str) -> Topic | None:
        return await self.session.scalar(
            select(Topic)
            .join(Topic.board)
            .options(selectinload(Topic.board))
            .where(Topic.id == topic_id, *self._public_topic_conditions())
        )

    async def _public_post(self, post_id: str) -> Post | None:
        return await self.session.scalar(
            select(Post)
            .join(Post.topic)
            .join(Topic.board)
            .options(selectinload(Post.topic))
            .where(Post.id == post_id, Post.deleted_at.is_(None), *self._public_topic_conditions())
        )

    async def _user_by_username(self, username: str) -> User:
        user = await self.session.scalar(
            select(User).where(User.username == username, User.status != "deleted")
        )
        if user is None:
            raise NotFoundError("user_not_found", "User not found")
        return user

    def _public_topic_conditions(self):
        return (
            Topic.deleted_at.is_(None),
            Topic.status != "hidden",
            Topic.visibility == "public",
            Board.visibility == "public",
        )

    def _can_view_private_profile(self, user: User, current_user: User | None) -> bool:
        if user.profile_visibility == "public":
            return True
        if current_user is None:
            return False
        if current_user.id == user.id or is_admin(current_user):
            return True
        return user.profile_visibility == "members"

    def _can_view_activity(self, user: User, current_user: User | None) -> bool:
        return user.show_activity and self._can_view_private_profile(user, current_user)

    def _clean_optional_text(self, value: str | None, *, max_length: int) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > max_length:
            raise ValidationError("invalid_profile_field", "Profile field is too long")
        return trimmed

    def _clean_url(self, value: str | None) -> str | None:
        cleaned = self._clean_optional_text(value, max_length=512)
        if cleaned is None:
            return None
        if URL_PATTERN.fullmatch(cleaned) is None:
            raise ValidationError("invalid_profile_url", "Profile URL must be http(s)")
        return cleaned

    def _excerpt(self, raw: str) -> str:
        text = unescape(TAG_PATTERN.sub(" ", raw)).strip()
        return text[:180] + ("…" if len(text) > 180 else "")
