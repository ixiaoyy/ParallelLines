from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.push import PushSubscription
from app.models.user import User
from app.schemas.push import (
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    PushSubscriptionStateResponse,
)


class PushSubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_state(self, current_user: User) -> PushSubscriptionStateResponse:
        subscription = await self._current_subscription(current_user.id)
        return PushSubscriptionStateResponse(
            subscription=(
                PushSubscriptionResponse.from_model(subscription) if subscription else None
            )
        )

    async def subscribe(
        self,
        payload: PushSubscriptionRequest,
        current_user: User,
    ) -> PushSubscriptionResponse:
        subscription = await self.session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
        if subscription is None:
            subscription = PushSubscription(endpoint=payload.endpoint, user_id=current_user.id)
            self.session.add(subscription)
        subscription.user_id = current_user.id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth_secret = payload.keys.auth
        subscription.user_agent = payload.user_agent
        subscription.enabled = True
        subscription.disabled_at = None
        await self.session.commit()
        await self.session.refresh(subscription)
        return PushSubscriptionResponse.from_model(subscription)

    async def unsubscribe(self, current_user: User) -> PushSubscriptionStateResponse:
        rows = list(
            await self.session.scalars(
                select(PushSubscription).where(
                    PushSubscription.user_id == current_user.id,
                    PushSubscription.enabled.is_(True),
                )
            )
        )
        now = utcnow()
        for row in rows:
            row.enabled = False
            row.disabled_at = now
        await self.session.commit()
        return PushSubscriptionStateResponse(subscription=None)

    async def _current_subscription(self, user_id: str) -> PushSubscription | None:
        return await self.session.scalar(
            select(PushSubscription)
            .where(PushSubscription.user_id == user_id, PushSubscription.enabled.is_(True))
            .order_by(desc(PushSubscription.updated_at))
        )
