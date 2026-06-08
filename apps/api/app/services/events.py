from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_global_moderator
from app.db.base import utcnow
from app.models.event import CalendarEvent, EventRsvp
from app.models.user import User
from app.schemas.events import (
    EventCreateRequest,
    EventLifecycleRequest,
    EventResponse,
    EventRsvpRequest,
    EventRsvpResponse,
)


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_events(
        self,
        *,
        current_user: User | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[EventResponse]:
        statement = select(CalendarEvent).order_by(CalendarEvent.start_at)
        if start_at:
            statement = statement.where(CalendarEvent.end_at >= start_at)
        if end_at:
            statement = statement.where(CalendarEvent.start_at <= end_at)
        events = list(await self.session.scalars(statement.limit(200)))
        counts = await self._going_counts([event.id for event in events])
        my_status = await self._my_statuses(
            [event.id for event in events],
            current_user.id if current_user else None,
        )
        return [
            EventResponse.from_model(
                event,
                going_count=counts.get(event.id, 0),
                my_rsvp_status=my_status.get(event.id),
            )
            for event in events
        ]

    async def create_event(self, payload: EventCreateRequest, current_user: User) -> EventResponse:
        start_at = self._aware(payload.start_at)
        end_at = self._aware(payload.end_at)
        if end_at <= start_at:
            raise ValidationError("event_invalid_time_range", "Event end must be after start.")
        if payload.rsvp_deadline and self._aware(payload.rsvp_deadline) > start_at:
            raise ValidationError(
                "event_invalid_rsvp_deadline",
                "RSVP deadline must be before event start.",
            )
        event = CalendarEvent(
            title=payload.title.strip(),
            description=(payload.description or "").strip() or None,
            topic_id=payload.topic_id,
            created_by_id=current_user.id,
            start_at=start_at,
            end_at=end_at,
            timezone=payload.timezone,
            location=(payload.location or "").strip() or None,
            capacity=payload.capacity,
            rsvp_deadline=self._aware(payload.rsvp_deadline) if payload.rsvp_deadline else None,
            reminder_minutes_before=payload.reminder_minutes_before,
            status="scheduled",
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return EventResponse.from_model(event, going_count=0)

    async def update_event_lifecycle(
        self,
        event_id: str,
        payload: EventLifecycleRequest,
        current_user: User,
    ) -> EventResponse:
        """Update an event lifecycle status for its creator or a global moderator.

        Key parameters identify the event, requested status, and acting user.
        Return value is the refreshed event response. Side effect: persists the
        event status and updates `updated_at` when the status changes.
        """

        event = await self._event(event_id)
        self._require_can_manage_event(event, current_user)
        if event.status != payload.status:
            event.status = payload.status
            event.updated_at = utcnow()
            await self.session.commit()
            await self.session.refresh(event)
        counts = await self._going_counts([event.id])
        my_status = await self._my_statuses([event.id], current_user.id)
        return EventResponse.from_model(
            event,
            going_count=counts.get(event.id, 0),
            my_rsvp_status=my_status.get(event.id),
        )

    async def delete_event(self, event_id: str, current_user: User) -> EventResponse:
        """Delete an event and its RSVP rows for its creator or a global moderator.

        Key parameters identify the event and acting user. Return value is the
        event snapshot from before deletion. Side effect: removes the event row;
        database cascade deletes linked RSVP rows.
        """

        event = await self._event(event_id)
        self._require_can_manage_event(event, current_user)
        counts = await self._going_counts([event.id])
        my_status = await self._my_statuses([event.id], current_user.id)
        response = EventResponse.from_model(
            event,
            going_count=counts.get(event.id, 0),
            my_rsvp_status=my_status.get(event.id),
        )
        await self.session.delete(event)
        await self.session.commit()
        return response

    async def rsvp_event(
        self,
        event_id: str,
        payload: EventRsvpRequest,
        current_user: User,
    ) -> EventRsvpResponse:
        event = await self._event(event_id)
        now = utcnow()
        if payload.status == "going":
            if event.status == "canceled":
                raise ValidationError("event_canceled", "Event is canceled.")
            deadline = event.rsvp_deadline or event.start_at
            if self._is_past(deadline, now):
                raise ValidationError("event_rsvp_closed", "RSVP is closed.")
            if event.capacity is not None and await self._going_count(event.id) >= event.capacity:
                raise ValidationError("event_capacity_full", "Event capacity is full.")
        rsvp = await self.session.scalar(
            select(EventRsvp)
            .options(selectinload(EventRsvp.user))
            .where(EventRsvp.event_id == event.id, EventRsvp.user_id == current_user.id)
        )
        if rsvp is None:
            rsvp = EventRsvp(event_id=event.id, user_id=current_user.id, status=payload.status)
            self.session.add(rsvp)
        rsvp.status = payload.status
        await self.session.commit()
        await self.session.refresh(rsvp, attribute_names=["user"])
        return EventRsvpResponse.from_model(rsvp)

    async def ical_feed(self) -> str:
        events = list(
            await self.session.scalars(select(CalendarEvent).order_by(CalendarEvent.start_at))
        )
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ParallelLines//Events//CN"]
        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@parallellines",
                    f"DTSTAMP:{self._ical_time(event.created_at)}",
                    f"DTSTART:{self._ical_time(event.start_at)}",
                    f"DTEND:{self._ical_time(event.end_at)}",
                    f"SUMMARY:{self._escape_ical(event.title)}",
                    f"DESCRIPTION:{self._escape_ical(event.description or '')}",
                    f"STATUS:{'CANCELLED' if event.status == 'canceled' else 'CONFIRMED'}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    async def _event(self, event_id: str) -> CalendarEvent:
        event = await self.session.get(CalendarEvent, event_id)
        if event is None:
            raise NotFoundError("event_not_found", "Event not found")
        return event

    def _require_can_manage_event(self, event: CalendarEvent, current_user: User) -> None:
        """Require creator or global moderator permission for an event management action.

        Key parameters are the loaded event and acting user. Return value is
        none. Side effect: raises `PermissionDeniedError` when the user cannot
        manage this event.
        """

        if not self._can_manage_event(event, current_user):
            raise PermissionDeniedError("permission_denied", "Permission denied")

    def _can_manage_event(self, event: CalendarEvent, current_user: User) -> bool:
        """Return whether a user may cancel or delete an event.

        Key parameters are the loaded event and acting user. Return value is a
        boolean permission decision. Side effects: none.
        """

        return event.created_by_id == current_user.id or is_global_moderator(current_user)

    async def _going_count(self, event_id: str) -> int:
        count = await self.session.scalar(
            select(func.count(EventRsvp.id)).where(
                EventRsvp.event_id == event_id,
                EventRsvp.status == "going",
            )
        )
        return int(count or 0)

    async def _going_counts(self, event_ids: list[str]) -> dict[str, int]:
        if not event_ids:
            return {}
        rows = await self.session.execute(
            select(EventRsvp.event_id, func.count(EventRsvp.id))
            .where(EventRsvp.event_id.in_(event_ids), EventRsvp.status == "going")
            .group_by(EventRsvp.event_id)
        )
        return {str(event_id): int(count) for event_id, count in rows}

    async def _my_statuses(self, event_ids: list[str], user_id: str | None) -> dict[str, str]:
        if not event_ids or not user_id:
            return {}
        rows = await self.session.execute(
            select(EventRsvp.event_id, EventRsvp.status).where(
                EventRsvp.event_id.in_(event_ids),
                EventRsvp.user_id == user_id,
            )
        )
        return {str(event_id): str(status) for event_id, status in rows}

    def _aware(self, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def _is_past(self, value: datetime, now: datetime) -> bool:
        if value.tzinfo is None:
            now = now.replace(tzinfo=None)
        return value < now

    def _ical_time(self, value: datetime) -> str:
        aware = self._aware(value).astimezone(UTC)
        return aware.strftime("%Y%m%dT%H%M%SZ")

    def _escape_ical(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,")
