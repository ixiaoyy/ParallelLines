from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.event import CalendarEvent, EventRsvp


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    topic_id: str | None = Field(default=None, max_length=36)
    start_at: datetime
    end_at: datetime
    timezone: str = Field(default="UTC", max_length=64)
    location: str | None = Field(default=None, max_length=200)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    rsvp_deadline: datetime | None = None
    reminder_minutes_before: int = Field(default=60, ge=0, le=10_080)


class EventRsvpRequest(BaseModel):
    status: Literal["going", "canceled"] = "going"


class EventRsvpResponse(BaseModel):
    user_id: str
    username: str
    status: str
    reminder_sent_at: datetime | None = None

    @classmethod
    def from_model(cls, rsvp: EventRsvp) -> EventRsvpResponse:
        return cls(
            user_id=rsvp.user_id,
            username=rsvp.user.username,
            status=rsvp.status,
            reminder_sent_at=rsvp.reminder_sent_at,
        )


class EventResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    topic_id: str | None = None
    created_by_id: str
    start_at: datetime
    end_at: datetime
    timezone: str
    location: str | None = None
    capacity: int | None = None
    rsvp_deadline: datetime | None = None
    reminder_minutes_before: int
    going_count: int
    my_rsvp_status: str | None = None
    created_at: datetime

    @classmethod
    def from_model(
        cls,
        event: CalendarEvent,
        *,
        going_count: int,
        my_rsvp_status: str | None = None,
    ) -> EventResponse:
        return cls(
            id=event.id,
            title=event.title,
            description=event.description,
            topic_id=event.topic_id,
            created_by_id=event.created_by_id,
            start_at=event.start_at,
            end_at=event.end_at,
            timezone=event.timezone,
            location=event.location,
            capacity=event.capacity,
            rsvp_deadline=event.rsvp_deadline,
            reminder_minutes_before=event.reminder_minutes_before,
            going_count=going_count,
            my_rsvp_status=my_rsvp_status,
            created_at=event.created_at,
        )
