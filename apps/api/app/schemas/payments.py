from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.payment import PaymentEvent, SubscriptionPlan, UserSubscription


class SubscriptionPlanResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    price_cents: int
    currency: str
    interval: str
    entitlements: list[str] = Field(default_factory=list)
    active: bool

    @classmethod
    def from_model(cls, plan: SubscriptionPlan) -> SubscriptionPlanResponse:
        return cls(
            id=plan.id,
            slug=plan.slug,
            name=plan.name,
            description=plan.description,
            price_cents=plan.price_cents,
            currency=plan.currency,
            interval=plan.interval,
            entitlements=list(plan.entitlements or []),
            active=plan.active,
        )


class UserSubscriptionResponse(BaseModel):
    id: str | None = None
    plan: SubscriptionPlanResponse | None = None
    status: str
    provider: str | None = None
    provider_subscription_id: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    entitlements: list[str] = Field(default_factory=list)

    @classmethod
    def from_model(cls, subscription: UserSubscription | None) -> UserSubscriptionResponse:
        if subscription is None:
            return cls(status="none")
        active = (
            subscription.status == "active"
            and subscription.current_period_end
            >= datetime.now(subscription.current_period_end.tzinfo)
        )
        return cls(
            id=subscription.id,
            plan=SubscriptionPlanResponse.from_model(subscription.plan),
            status=subscription.status if active else "expired",
            provider=subscription.provider,
            provider_subscription_id=subscription.provider_subscription_id,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
            entitlements=list(subscription.plan.entitlements or []) if active else [],
        )


class PaymentWebhookResponse(BaseModel):
    event_id: str
    event_type: str
    processed: bool
    subscription_status: str | None = None


class PaymentEventResponse(BaseModel):
    id: str
    provider: str
    event_id: str
    event_type: str
    status: str
    signature_valid: bool
    amount_cents: int | None = None
    currency: str | None = None
    processed_at: datetime | None = None

    @classmethod
    def from_model(cls, event: PaymentEvent) -> PaymentEventResponse:
        return cls(
            id=event.id,
            provider=event.provider,
            event_id=event.event_id,
            event_type=event.event_type,
            status=event.status,
            signature_valid=event.signature_valid,
            amount_cents=event.amount_cents,
            currency=event.currency,
            processed_at=event.processed_at,
        )
