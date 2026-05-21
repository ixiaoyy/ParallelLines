from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.email import EmailDeliveryEvent, InboundEmail, UserEmailPreference
from app.schemas.common import ORMModel

DigestFrequency = Literal["off", "daily", "weekly"]
DeliveryEventType = Literal["delivered", "bounce", "complaint", "dropped"]


class EmailPreferenceUpdateRequest(BaseModel):
    email_enabled: bool | None = None
    notify_replied: bool | None = None
    notify_mentioned: bool | None = None
    notify_liked: bool | None = None
    notify_topic_new_post: bool | None = None
    notify_board_new_topic: bool | None = None
    digest_frequency: DigestFrequency | None = None


class EmailPreferenceResponse(ORMModel):
    email_enabled: bool
    notify_replied: bool
    notify_mentioned: bool
    notify_liked: bool
    notify_topic_new_post: bool
    notify_board_new_topic: bool
    digest_frequency: str
    last_digest_sent_at: datetime | None = None
    delivery_status: str
    disabled_reason: str | None = None
    updated_at: datetime

    @classmethod
    def from_model(cls, preference: UserEmailPreference) -> "EmailPreferenceResponse":
        return cls(
            email_enabled=preference.email_enabled,
            notify_replied=preference.notify_replied,
            notify_mentioned=preference.notify_mentioned,
            notify_liked=preference.notify_liked,
            notify_topic_new_post=preference.notify_topic_new_post,
            notify_board_new_topic=preference.notify_board_new_topic,
            digest_frequency=preference.digest_frequency,
            last_digest_sent_at=preference.last_digest_sent_at,
            delivery_status=preference.delivery_status,
            disabled_reason=preference.disabled_reason,
            updated_at=preference.updated_at,
        )


class EmailDeliveryWebhookRequest(BaseModel):
    email: EmailStr
    event_type: DeliveryEventType
    kind: str | None = Field(default=None, max_length=64)
    provider_message_id: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)
    payload: dict[str, object] = Field(default_factory=dict)


class EmailDeliveryEventResponse(ORMModel):
    id: str
    user_id: str | None = None
    email: str
    event_type: str
    kind: str | None = None
    provider_message_id: str | None = None
    reason: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, event: EmailDeliveryEvent) -> "EmailDeliveryEventResponse":
        return cls(
            id=event.id,
            user_id=event.user_id,
            email=event.email,
            event_type=event.event_type,
            kind=event.kind,
            provider_message_id=event.provider_message_id,
            reason=event.reason,
            created_at=event.created_at,
        )


class InboundEmailWebhookRequest(BaseModel):
    from_email: EmailStr
    raw_md: str = Field(min_length=1, max_length=20_000)
    topic_id: str | None = None
    post_id: str | None = None
    provider_message_id: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)


class InboundEmailResponse(ORMModel):
    id: str
    from_email: str
    user_id: str | None = None
    topic_id: str | None = None
    post_id: str | None = None
    provider_message_id: str | None = None
    status: str
    reason: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, inbound: InboundEmail) -> "InboundEmailResponse":
        return cls(
            id=inbound.id,
            from_email=inbound.from_email,
            user_id=inbound.user_id,
            topic_id=inbound.topic_id,
            post_id=inbound.post_id,
            provider_message_id=inbound.provider_message_id,
            status=inbound.status,
            reason=inbound.reason,
            created_at=inbound.created_at,
        )
