from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.forum import NotificationLevel
from app.models.interaction import Notification


class BoardFollowRequest(BaseModel):
    notification_level: NotificationLevel = "watching"


class BoardFollowResponse(BaseModel):
    board_id: str
    board_slug: str
    following: bool
    role: str | None
    notification_level: NotificationLevel | None
    follower_count: int


class InteractionStateResponse(BaseModel):
    target_type: Literal["post", "topic"]
    target_id: str
    active: bool
    count: int


class NotificationResponse(BaseModel):
    id: str
    type: str
    topic_id: str | None = None
    post_id: str | None = None
    actor_id: str | None = None
    actor_name: str | None = None
    data: dict[str, object]
    read_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, notification: Notification) -> NotificationResponse:
        return cls(
            id=notification.id,
            type=notification.type,
            topic_id=notification.topic_id,
            post_id=notification.post_id,
            actor_id=notification.actor_id,
            actor_name=notification.actor.username if notification.actor else None,
            data=notification.data,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int


class NotificationReadRequest(BaseModel):
    ids: list[str] | None = Field(default=None, max_length=100)


class NotificationReadResponse(BaseModel):
    updated_count: int
    unread_count: int


class NotificationStreamResponse(BaseModel):
    unread_count: int
    notifications: list[NotificationResponse]


class TopicNotificationLevelRequest(BaseModel):
    notification_level: NotificationLevel


class TopicNotificationLevelResponse(BaseModel):
    topic_id: str
    notification_level: NotificationLevel
    last_read_post_number: int
