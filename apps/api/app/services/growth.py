from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.growth import REVIEW_ONLY_LEVEL, clamp_display_level, level_for_experience
from app.db.base import new_random_suffix, utcnow
from app.models.user import User, UserPointEvent


@dataclass(frozen=True)
class GrowthRule:
    points: int
    experience: int
    daily_points_cap: int | None = None
    daily_experience_cap: int | None = None


GROWTH_RULES: dict[str, GrowthRule] = {
    "email_verified": GrowthRule(points=20, experience=20),
    "daily_login": GrowthRule(
        points=5,
        experience=5,
        daily_points_cap=5,
        daily_experience_cap=5,
    ),
    "topic_created": GrowthRule(
        points=5,
        experience=5,
        daily_points_cap=25,
        daily_experience_cap=25,
    ),
    "post_created": GrowthRule(
        points=1,
        experience=1,
        daily_points_cap=20,
        daily_experience_cap=80,
    ),
    "content_liked": GrowthRule(
        points=1,
        experience=1,
        daily_points_cap=20,
        daily_experience_cap=20,
    ),
    "content_bookmarked": GrowthRule(
        points=1,
        experience=1,
        daily_points_cap=20,
        daily_experience_cap=20,
    ),
    "topic_replied": GrowthRule(
        points=1,
        experience=1,
        daily_points_cap=20,
        daily_experience_cap=20,
    ),
    "invite_accepted_inviter": GrowthRule(
        points=10,
        experience=10,
        daily_points_cap=50,
        daily_experience_cap=50,
    ),
    "invite_accepted_invitee": GrowthRule(
        points=5,
        experience=5,
        daily_points_cap=25,
        daily_experience_cap=25,
    ),
}


class GrowthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def award(
        self,
        user_id: str,
        source_type: str,
        *,
        source_id: str | None = None,
        actor_id: str | None = None,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserPointEvent | None:
        rule = GROWTH_RULES[source_type]
        stable_key = idempotency_key or self._idempotency_key(
            source_type=source_type,
            user_id=user_id,
            source_id=source_id,
            actor_id=actor_id,
        )
        return await self._apply_delta(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            points_delta=rule.points,
            experience_delta=rule.experience,
            actor_id=actor_id,
            note=note,
            idempotency_key=stable_key,
            daily_points_cap=rule.daily_points_cap,
            daily_experience_cap=rule.daily_experience_cap,
        )

    async def adjust_user(
        self,
        user: User,
        *,
        points_delta: int = 0,
        experience_delta: int = 0,
        actor_id: str | None,
        note: str | None,
    ) -> UserPointEvent | None:
        if points_delta == 0 and experience_delta == 0:
            return None
        return await self._apply_delta(
            user_id=user.id,
            source_type="admin_adjustment",
            source_id=None,
            points_delta=points_delta,
            experience_delta=experience_delta,
            actor_id=actor_id,
            note=note,
            idempotency_key=f"admin_adjustment:{user.id}:{new_random_suffix(8)}",
            daily_points_cap=None,
            daily_experience_cap=None,
            loaded_user=user,
        )

    async def _apply_delta(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str | None,
        points_delta: int,
        experience_delta: int,
        actor_id: str | None,
        note: str | None,
        idempotency_key: str,
        daily_points_cap: int | None,
        daily_experience_cap: int | None,
        loaded_user: User | None = None,
    ) -> UserPointEvent | None:
        existing_event = await self.session.scalar(
            select(UserPointEvent).where(UserPointEvent.idempotency_key == idempotency_key)
        )
        if existing_event is not None:
            return existing_event

        user = loaded_user or await self.session.get(User, user_id)
        if user is None:
            return None

        capped_points_delta = await self._cap_positive_delta(
            user_id=user.id,
            source_type=source_type,
            requested_delta=points_delta,
            daily_cap=daily_points_cap,
            column=UserPointEvent.points_delta,
        )
        capped_experience_delta = await self._cap_positive_delta(
            user_id=user.id,
            source_type=source_type,
            requested_delta=experience_delta,
            daily_cap=daily_experience_cap,
            column=UserPointEvent.experience_delta,
        )

        next_points = max(0, (user.points_balance or 0) + capped_points_delta)
        next_experience = max(0, (user.experience_total or 0) + capped_experience_delta)
        actual_points_delta = next_points - (user.points_balance or 0)
        actual_experience_delta = next_experience - (user.experience_total or 0)

        user.points_balance = next_points
        user.experience_total = next_experience
        user.level = self._next_display_level(user.level, next_experience)

        event = UserPointEvent(
            user_id=user.id,
            source_type=source_type,
            source_id=source_id,
            points_delta=actual_points_delta,
            experience_delta=actual_experience_delta,
            balance_after=user.points_balance,
            experience_after=user.experience_total,
            level_after=user.level,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            note=note,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    def _next_display_level(self, current_level: int | None, next_experience: int) -> int:
        if clamp_display_level(current_level) >= REVIEW_ONLY_LEVEL:
            return REVIEW_ONLY_LEVEL
        return level_for_experience(next_experience)

    async def _cap_positive_delta(
        self,
        *,
        user_id: str,
        source_type: str,
        requested_delta: int,
        daily_cap: int | None,
        column,
    ) -> int:
        if requested_delta <= 0 or daily_cap is None:
            return requested_delta

        day_start, day_end = self._today_window()
        used_today = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(column), 0)).where(
                    UserPointEvent.user_id == user_id,
                    UserPointEvent.source_type == source_type,
                    UserPointEvent.created_at >= day_start,
                    UserPointEvent.created_at < day_end,
                    column > 0,
                )
            )
            or 0
        )
        remaining = max(0, daily_cap - used_today)
        return min(requested_delta, remaining)

    def _today_window(self) -> tuple[datetime, datetime]:
        now = utcnow()
        day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
        return day_start, day_start + timedelta(days=1)

    def _idempotency_key(
        self,
        *,
        source_type: str,
        user_id: str,
        source_id: str | None,
        actor_id: str | None,
    ) -> str:
        target = source_id or user_id
        actor = actor_id or "system"
        return f"{source_type}:{user_id}:{target}:{actor}"
