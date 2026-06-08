from datetime import datetime

from fastapi import APIRouter
from starlette.responses import Response

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.events import (
    EventCreateRequest,
    EventLifecycleRequest,
    EventResponse,
    EventRsvpRequest,
    EventRsvpResponse,
)
from app.services.events import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=ApiResponse[list[EventResponse]])
async def list_events(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ApiResponse[list[EventResponse]]:
    return ApiResponse(
        data=await EventService(session).list_events(
            current_user=current_user,
            start_at=start_at,
            end_at=end_at,
        )
    )


@router.post("", response_model=ApiResponse[EventResponse], status_code=201)
async def create_event(
    payload: EventCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EventResponse]:
    return ApiResponse(data=await EventService(session).create_event(payload, current_user))


@router.put("/{event_id}/lifecycle", response_model=ApiResponse[EventResponse])
async def update_event_lifecycle(
    event_id: str,
    payload: EventLifecycleRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EventResponse]:
    """Update an event lifecycle status for the creator or global moderators.

    Key parameters are the path event id, lifecycle payload, database session,
    and authenticated user. Return value is the updated event envelope. Side
    effect: persists a status transition such as scheduled -> canceled.
    """

    return ApiResponse(
        data=await EventService(session).update_event_lifecycle(event_id, payload, current_user)
    )


@router.delete("/{event_id}", response_model=ApiResponse[EventResponse])
async def delete_event(
    event_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EventResponse]:
    """Delete an event for the creator or global moderators.

    Key parameters are the path event id, database session, and authenticated
    user. Return value is the deleted event snapshot. Side effect: removes the
    event and cascades its RSVP rows in the database.
    """

    return ApiResponse(data=await EventService(session).delete_event(event_id, current_user))


@router.put("/{event_id}/rsvp", response_model=ApiResponse[EventRsvpResponse])
async def rsvp_event(
    event_id: str,
    payload: EventRsvpRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EventRsvpResponse]:
    return ApiResponse(data=await EventService(session).rsvp_event(event_id, payload, current_user))


@router.get("/calendar.ics")
async def calendar_ics(session: SessionDep) -> Response:
    return Response(
        content=await EventService(session).ical_feed(),
        media_type="text/calendar; charset=utf-8",
    )
