from datetime import datetime

from fastapi import APIRouter
from starlette.responses import Response

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.events import (
    EventCreateRequest,
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
