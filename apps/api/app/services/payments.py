from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.moderation import AuditLog
from app.models.payment import PaymentEvent, SubscriptionPlan, UserSubscription
from app.models.user import User
from app.schemas.payments import (
    PaymentEventResponse,
    PaymentWebhookResponse,
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)

DEFAULT_PLAN = {
    "slug": "supporter",
    "name": "支持者会员",
    "description": "解锁付费社区权益、支持站点持续运营。",
    "price_cents": 990,
    "currency": "CNY",
    "interval": "month",
    "entitlements": ["paid_member", "premium_board_access"],
}


class PaymentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def list_plans(self) -> list[SubscriptionPlanResponse]:
        await self._ensure_default_plan()
        plans = list(
            await self.session.scalars(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.active.is_(True))
                .order_by(SubscriptionPlan.price_cents)
            )
        )
        return [SubscriptionPlanResponse.from_model(plan) for plan in plans]

    async def current_subscription(self, current_user: User) -> UserSubscriptionResponse:
        subscription = await self._current_subscription(current_user.id)
        if subscription and subscription.status == "active" and self._is_expired(subscription):
            subscription.status = "expired"
            await self.session.commit()
            await self.session.refresh(subscription, attribute_names=["plan"])
        return UserSubscriptionResponse.from_model(subscription)

    async def list_payment_events(
        self,
        current_user: User,
        *,
        limit: int = 50,
    ) -> list[PaymentEventResponse]:
        self._require_admin(current_user)
        events = list(
            await self.session.scalars(
                select(PaymentEvent).order_by(desc(PaymentEvent.created_at)).limit(limit)
            )
        )
        return [PaymentEventResponse.from_model(event) for event in events]

    async def handle_webhook(
        self,
        provider: str,
        body: bytes,
        signature: str | None,
    ) -> PaymentWebhookResponse:
        if not self._verify_signature(body, signature):
            raise PermissionDeniedError("payment_webhook_signature_invalid", "Invalid signature")
        await self._ensure_default_plan()
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("payment_webhook_invalid_json", "Invalid webhook JSON") from exc
        event_id = str(payload.get("id") or "")
        event_type = str(payload.get("type") or "")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if not event_id or not event_type:
            raise ValidationError("payment_webhook_invalid_payload", "Missing event id or type")

        existing = await self.session.scalar(
            select(PaymentEvent).where(
                PaymentEvent.provider == provider,
                PaymentEvent.event_id == event_id,
            )
        )
        if existing:
            return PaymentWebhookResponse(
                event_id=existing.event_id,
                event_type=existing.event_type,
                processed=True,
                subscription_status=None,
            )

        plan = await self._plan_by_slug(str(data.get("plan_slug") or DEFAULT_PLAN["slug"]))
        user = await self.session.get(User, str(data.get("user_id") or ""))
        subscription: UserSubscription | None = None
        status = "ignored"
        now = utcnow()
        if user and event_type in {"checkout.session.completed", "invoice.paid"}:
            subscription = await self._activate_subscription(provider, user, plan, data, now)
            status = "processed"
        elif event_type == "invoice.payment_failed":
            subscription = await self._mark_provider_subscription(
                provider,
                str(data.get("subscription_id") or ""),
                "past_due",
            )
            status = "payment_failed"
        elif event_type in {"customer.subscription.deleted", "subscription.expired"}:
            subscription = await self._mark_provider_subscription(
                provider,
                str(data.get("subscription_id") or ""),
                "expired",
            )
            status = "processed"

        event = PaymentEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            user_id=user.id if user else None,
            plan_id=plan.id if plan else None,
            subscription_id=subscription.id if subscription else None,
            amount_cents=self._optional_int(data.get("amount_cents")),
            currency=str(data.get("currency") or plan.currency if plan else "CNY"),
            status=status,
            signature_valid=True,
            payload=self._redacted_payload(payload),
            processed_at=now,
        )
        self.session.add(event)
        self.session.add(
            AuditLog(
                actor_id=user.id if user else None,
                action="payment_webhook_processed",
                target_type="payment_event",
                target_id=event_id,
                data={"provider": provider, "event_type": event_type, "status": status},
                created_at=now,
            )
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
        return PaymentWebhookResponse(
            event_id=event_id,
            event_type=event_type,
            processed=True,
            subscription_status=subscription.status if subscription else None,
        )

    async def _ensure_default_plan(self) -> SubscriptionPlan:
        plan = await self._plan_by_slug(DEFAULT_PLAN["slug"])
        if plan:
            return plan
        plan = SubscriptionPlan(**DEFAULT_PLAN)
        self.session.add(plan)
        await self.session.commit()
        return plan

    async def _plan_by_slug(self, slug: str) -> SubscriptionPlan | None:
        return await self.session.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == slug)
        )

    async def _current_subscription(self, user_id: str) -> UserSubscription | None:
        return await self.session.scalar(
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan))
            .where(UserSubscription.user_id == user_id)
            .order_by(desc(UserSubscription.current_period_end))
        )

    async def _activate_subscription(
        self,
        provider: str,
        user: User,
        plan: SubscriptionPlan,
        data: dict[str, Any],
        now: datetime,
    ) -> UserSubscription:
        provider_subscription_id = str(data.get("subscription_id") or "")
        if not provider_subscription_id:
            raise ValidationError("payment_webhook_invalid_payload", "Missing subscription id")
        subscription = await self.session.scalar(
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan))
            .where(
                UserSubscription.provider == provider,
                UserSubscription.provider_subscription_id == provider_subscription_id,
            )
        )
        if subscription is None:
            subscription = UserSubscription(
                user_id=user.id,
                plan_id=plan.id,
                provider=provider,
                provider_customer_id=str(data.get("customer_id") or "") or None,
                provider_subscription_id=provider_subscription_id,
                current_period_start=now,
                current_period_end=self._period_end(data, now),
            )
            self.session.add(subscription)
        subscription.user_id = user.id
        subscription.plan_id = plan.id
        subscription.status = "active"
        subscription.current_period_start = now
        subscription.current_period_end = self._period_end(data, now)
        subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end") or False)
        await self.session.flush()
        await self.session.refresh(subscription, attribute_names=["plan"])
        return subscription

    async def _mark_provider_subscription(
        self,
        provider: str,
        provider_subscription_id: str,
        status: str,
    ) -> UserSubscription | None:
        if not provider_subscription_id:
            return None
        subscription = await self.session.scalar(
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan))
            .where(
                UserSubscription.provider == provider,
                UserSubscription.provider_subscription_id == provider_subscription_id,
            )
        )
        if subscription:
            subscription.status = status
            if status == "expired":
                subscription.current_period_end = utcnow()
        return subscription

    def _verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        digest = hmac.new(
            self.settings.payment_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        expected_values = {digest, f"sha256={digest}"}
        return any(hmac.compare_digest(signature, expected) for expected in expected_values)

    def _period_end(self, data: dict[str, Any], now: datetime) -> datetime:
        raw = data.get("current_period_end")
        if isinstance(raw, str) and raw:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return now + timedelta(days=30)

    def _is_expired(self, subscription: UserSubscription) -> bool:
        now = utcnow()
        end = subscription.current_period_end
        if end.tzinfo is None:
            now = now.replace(tzinfo=None)
        return end < now

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        return int(value)

    def _redacted_payload(self, payload: dict[str, Any]) -> dict[str, object]:
        redacted = dict(payload)
        for key in ("secret", "token", "card", "payment_method"):
            if key in redacted:
                redacted[key] = "[redacted]"
        return redacted
