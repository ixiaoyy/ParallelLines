from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.push import PushSubscription
from app.schemas.common import ORMModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: PushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=500)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith("https://"):
            raise ValueError("push endpoint must use https")
        return trimmed


class PushSubscriptionResponse(ORMModel):
    id: str
    endpoint_excerpt: str
    enabled: bool
    user_agent: str | None = None
    last_sent_at: datetime | None = None
    disabled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, subscription: PushSubscription) -> PushSubscriptionResponse:
        endpoint = subscription.endpoint
        excerpt = endpoint if len(endpoint) <= 80 else f"{endpoint[:44]}…{endpoint[-24:]}"
        return cls(
            id=subscription.id,
            endpoint_excerpt=excerpt,
            enabled=subscription.enabled,
            user_agent=subscription.user_agent,
            last_sent_at=subscription.last_sent_at,
            disabled_at=subscription.disabled_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )


class PushSubscriptionStateResponse(BaseModel):
    subscription: PushSubscriptionResponse | None = None
    supported: bool = True
    preference_hint: str = "push follows notification and quiet-hour preferences"
