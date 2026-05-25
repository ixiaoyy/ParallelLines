from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.trust import AUTO_TRUST_LEVEL_MAX, clamp_trust_level
from app.db.base import new_random_suffix, utcnow
from app.models.badge import BadgeDefinition, UserBadge, UserTrustLevelEvent
from app.models.forum import Post, Topic
from app.models.user import User, UserPointEvent
from app.schemas.badges import BadgeResponse, UserBadgeResponse


@dataclass(frozen=True)
class DefaultBadge:
    slug: str
    name: str
    description: str
    category: str
    icon: str
    trust_level_required: int = 0


DEFAULT_BADGES: tuple[DefaultBadge, ...] = (
    DefaultBadge(
        slug="verified-member",
        name="已验证成员",
        description="完成邮箱验证并激活账号。",
        category="account",
        icon="✓",
    ),
    DefaultBadge(
        slug="first-topic",
        name="第一条主题",
        description="发布第一条公开主题。",
        category="participation",
        icon="✦",
    ),
    DefaultBadge(
        slug="first-reply",
        name="第一次回复",
        description="在公开讨论中完成第一次回复。",
        category="participation",
        icon="↩",
    ),
    DefaultBadge(
        slug="received-like",
        name="收到认可",
        description="公开主题或回复第一次被其他成员点赞。",
        category="reputation",
        icon="♥",
    ),
    DefaultBadge(
        slug="trusted-regular",
        name="可信常驻",
        description="达到信任等级 2，拥有更宽松的正常使用边界。",
        category="trust",
        icon="◆",
        trust_level_required=2,
    ),
)


class BadgeTrustService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_badges(self) -> list[BadgeResponse]:
        await self.ensure_default_badges()
        badges = list(
            await self.session.scalars(
                select(BadgeDefinition).order_by(
                    BadgeDefinition.category,
                    BadgeDefinition.trust_level_required,
                    BadgeDefinition.name,
                )
            )
        )
        return [BadgeResponse.from_model(badge) for badge in badges]

    async def list_user_badges(
        self,
        user_id: str,
        *,
        active_only: bool = True,
    ) -> list[UserBadgeResponse]:
        statement = (
            select(UserBadge)
            .options(selectinload(UserBadge.badge))
            .where(UserBadge.user_id == user_id)
            .order_by(UserBadge.created_at.desc())
        )
        if active_only:
            statement = statement.where(UserBadge.revoked_at.is_(None))
        user_badges = list(await self.session.scalars(statement))
        return [UserBadgeResponse.from_model(user_badge) for user_badge in user_badges]

    async def grant_badge(
        self,
        *,
        user_id: str,
        badge_slug: str,
        source_type: str,
        source_id: str | None = None,
        actor_id: str | None = None,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserBadge | None:
        await self.ensure_default_badges()
        badge = await self.session.scalar(
            select(BadgeDefinition).where(
                BadgeDefinition.slug == badge_slug,
                BadgeDefinition.active.is_(True),
            )
        )
        if badge is None:
            raise NotFoundError("badge_not_found", "Badge not found")

        stable_key = idempotency_key or self._idempotency_key(
            user_id=user_id,
            badge_slug=badge_slug,
            source_type=source_type,
            source_id=source_id,
            actor_id=actor_id,
        )
        existing_by_key = await self.session.scalar(
            select(UserBadge)
            .options(selectinload(UserBadge.badge))
            .where(UserBadge.idempotency_key == stable_key)
        )
        if existing_by_key is not None:
            return existing_by_key

        active_existing = await self.session.scalar(
            select(UserBadge)
            .options(selectinload(UserBadge.badge))
            .where(
                UserBadge.user_id == user_id,
                UserBadge.badge_id == badge.id,
                UserBadge.revoked_at.is_(None),
            )
        )
        if active_existing is not None:
            return active_existing

        if await self.session.get(User, user_id) is None:
            return None

        user_badge = UserBadge(
            user_id=user_id,
            badge_id=badge.id,
            badge=badge,
            source_type=source_type,
            source_id=source_id,
            granted_by_id=actor_id,
            idempotency_key=stable_key,
            note=note,
        )
        self.session.add(user_badge)
        await self.session.flush()
        return user_badge

    async def revoke_badge(
        self,
        *,
        user_id: str,
        badge_slug: str,
        actor_id: str,
        reason: str | None = None,
    ) -> UserBadge:
        user_badge = await self.session.scalar(
            select(UserBadge)
            .join(UserBadge.badge)
            .options(selectinload(UserBadge.badge))
            .where(
                UserBadge.user_id == user_id,
                BadgeDefinition.slug == badge_slug,
                UserBadge.revoked_at.is_(None),
            )
        )
        if user_badge is None:
            raise NotFoundError("user_badge_not_found", "User badge not found")
        user_badge.revoked_at = utcnow()
        user_badge.revoked_by_id = actor_id
        user_badge.revoke_reason = reason.strip() if reason else None
        await self.session.flush()
        return user_badge

    async def recompute_trust(
        self,
        user: User,
        *,
        source_type: str,
        source_id: str | None = None,
        actor_id: str | None = None,
        note: str | None = None,
    ) -> UserTrustLevelEvent | None:
        previous_level = clamp_trust_level(user.trust_level)
        next_level = await self._computed_trust_level(user)
        if previous_level >= 4 and user.status == "active":
            next_level = 4
        if next_level == previous_level:
            if next_level >= 2:
                await self.grant_badge(
                    user_id=user.id,
                    badge_slug="trusted-regular",
                    source_type="trust_level",
                    source_id=str(next_level),
                    actor_id=actor_id,
                    note="达到可信常驻等级",
                    idempotency_key=f"badge:trusted-regular:{user.id}",
                )
            return None

        user.trust_level = next_level
        user.trust_level_changed_at = utcnow()
        event = UserTrustLevelEvent(
            user_id=user.id,
            previous_level=previous_level,
            next_level=next_level,
            source_type=source_type,
            source_id=source_id,
            actor_id=actor_id,
            note=note,
        )
        self.session.add(event)
        await self.session.flush()
        if next_level >= 2:
            await self.grant_badge(
                user_id=user.id,
                badge_slug="trusted-regular",
                source_type="trust_level",
                source_id=str(next_level),
                actor_id=actor_id,
                note="达到可信常驻等级",
                idempotency_key=f"badge:trusted-regular:{user.id}",
            )
        return event

    async def ensure_default_badges(self) -> None:
        existing = {
            badge.slug: badge
            for badge in await self.session.scalars(select(BadgeDefinition))
        }
        for default_badge in DEFAULT_BADGES:
            if default_badge.slug in existing:
                continue
            self.session.add(
                BadgeDefinition(
                    slug=default_badge.slug,
                    name=default_badge.name,
                    description=default_badge.description,
                    category=default_badge.category,
                    icon=default_badge.icon,
                    trust_level_required=default_badge.trust_level_required,
                    active=True,
                )
            )
        await self.session.flush()

    async def _computed_trust_level(self, user: User) -> int:
        if user.status != "active":
            return 0

        topic_count = int(
            await self.session.scalar(
                select(func.count(Topic.id)).where(
                    Topic.user_id == user.id,
                    Topic.deleted_at.is_(None),
                    Topic.visibility == "public",
                )
            )
            or 0
        )
        post_count = int(
            await self.session.scalar(
                select(func.count(Post.id))
                .join(Topic, Topic.id == Post.topic_id)
                .where(
                    Post.user_id == user.id,
                    Post.deleted_at.is_(None),
                    Topic.visibility == "public",
                    Topic.deleted_at.is_(None),
                )
            )
            or 0
        )
        liked_events = int(
            await self.session.scalar(
                select(func.count(UserPointEvent.id)).where(
                    UserPointEvent.user_id == user.id,
                    UserPointEvent.source_type == "content_liked",
                    UserPointEvent.experience_delta > 0,
                )
            )
            or 0
        )

        experience_total = int(user.experience_total or 0)
        next_level = 0
        if experience_total >= 20:
            next_level = 1
        if experience_total >= 150 and topic_count >= 1 and post_count >= 3:
            next_level = 2
        if experience_total >= 600 and topic_count >= 3 and post_count >= 10 and liked_events >= 5:
            next_level = 3
        return min(next_level, AUTO_TRUST_LEVEL_MAX)

    def _idempotency_key(
        self,
        *,
        user_id: str,
        badge_slug: str,
        source_type: str,
        source_id: str | None,
        actor_id: str | None,
    ) -> str:
        source = source_id or user_id
        actor = actor_id or "system"
        return f"badge:{badge_slug}:{user_id}:{source_type}:{source}:{actor}:{new_random_suffix(8)}"
