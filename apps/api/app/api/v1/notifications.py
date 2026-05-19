import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.interactions import (
    NotificationListResponse,
    NotificationReadRequest,
    NotificationReadResponse,
    NotificationResponse,
)
from app.services.interactions import InteractionService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=ApiResponse[NotificationListResponse])
async def list_notifications(
    session: SessionDep,
    current_user: CurrentUserDep,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[NotificationListResponse]:
    notifications, unread_count = await InteractionService(session).list_notifications(
        current_user,
        unread_only=unread_only,
        limit=limit,
    )
    return ApiResponse(
        data=NotificationListResponse(
            notifications=[
                NotificationResponse.from_model(notification) for notification in notifications
            ],
            unread_count=unread_count,
        )
    )


@router.put("/read", response_model=ApiResponse[NotificationReadResponse])
async def mark_notifications_read(
    payload: NotificationReadRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[NotificationReadResponse]:
    state = await InteractionService(session).mark_notifications_read(
        current_user,
        ids=payload.ids,
    )
    return ApiResponse(data=state)


@router.get("/stream")
async def stream_notifications(
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
    poll_seconds: Annotated[float, Query(ge=1, le=30)] = 5,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
    once: bool = False,
) -> StreamingResponse:
    async def events():
        last_payload: str | None = None
        service = InteractionService(session)

        while True:
            if await request.is_disconnected():
                break

            snapshot = await service.notification_stream_snapshot(current_user, limit=limit)
            payload = snapshot.model_dump_json()

            if payload != last_payload:
                last_payload = payload
                yield f"event: notifications\ndata: {payload}\n\n"
            else:
                yield ": heartbeat\n\n"

            await session.commit()
            if once:
                break
            await asyncio.sleep(poll_seconds)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
