import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.chat import (
    ChatChannelCreateRequest,
    ChatChannelResponse,
    ChatMessageCreateRequest,
    ChatMessagePageResponse,
    ChatMessageResponse,
    ChatPresenceResponse,
    ChatPresenceUpdateRequest,
)
from app.schemas.common import ApiResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/channels", response_model=ApiResponse[list[ChatChannelResponse]])
async def list_chat_channels(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[ChatChannelResponse]]:
    return ApiResponse(data=await ChatService(session).list_channels(current_user))


@router.post("/channels", response_model=ApiResponse[ChatChannelResponse], status_code=201)
async def create_chat_channel(
    payload: ChatChannelCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ChatChannelResponse]:
    return ApiResponse(data=await ChatService(session).create_channel(payload, current_user))


@router.get(
    "/channels/{channel_id}/messages",
    response_model=ApiResponse[ChatMessagePageResponse],
)
async def list_chat_messages(
    channel_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    before_id: str | None = None,
    after_id: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[ChatMessagePageResponse]:
    return ApiResponse(
        data=await ChatService(session).list_messages(
            channel_id,
            current_user,
            limit=limit,
            before_id=before_id,
            after_id=after_id,
            query=q,
        )
    )


@router.post(
    "/channels/{channel_id}/messages",
    response_model=ApiResponse[ChatMessageResponse],
    status_code=201,
)
async def send_chat_message(
    channel_id: str,
    payload: ChatMessageCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ChatMessageResponse]:
    return ApiResponse(
        data=await ChatService(session).send_message(channel_id, payload, current_user)
    )


@router.get(
    "/channels/{channel_id}/presence",
    response_model=ApiResponse[list[ChatPresenceResponse]],
)
async def list_chat_presence(
    channel_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[ChatPresenceResponse]]:
    return ApiResponse(data=await ChatService(session).list_presence(channel_id, current_user))


@router.put(
    "/channels/{channel_id}/presence",
    response_model=ApiResponse[ChatPresenceResponse],
)
async def update_chat_presence(
    channel_id: str,
    payload: ChatPresenceUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ChatPresenceResponse]:
    return ApiResponse(
        data=await ChatService(session).update_presence(channel_id, payload, current_user)
    )


@router.get("/channels/{channel_id}/stream")
async def stream_chat_channel(
    channel_id: str,
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
    after_id: str | None = None,
    poll_seconds: Annotated[float, Query(ge=1, le=30)] = 3,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    once: bool = False,
) -> StreamingResponse:
    async def events():
        last_message_id = after_id
        while True:
            if await request.is_disconnected():
                break

            snapshot = await ChatService(session).stream_snapshot(
                channel_id,
                current_user,
                after_id=last_message_id,
                limit=limit,
            )
            if snapshot.messages:
                last_message_id = snapshot.messages[-1].id
            yield f"event: chat\ndata: {snapshot.model_dump_json()}\n\n"
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
