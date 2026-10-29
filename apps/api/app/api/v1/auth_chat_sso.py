from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep, TokenDep
from app.core.exceptions import ValidationError
from app.schemas.chat_sso import (
    ChatSsoApproveRequest,
    ChatSsoApproveResponse,
    ChatSsoExchangeRequest,
    ChatSsoExchangeResponse,
    ChatSsoStateRequest,
    ChatSsoStateResponse,
)
from app.schemas.common import ApiResponse
from app.services.chat_sso import ChatSsoService


class ChatSsoRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def without_sensitive_validation_input(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                # The main generic validation handler echoes input; opaque approval values must not.
                raise ValidationError(
                    "invalid_chat_sso_request", "Invalid chat SSO request"
                ) from None

        return without_sensitive_validation_input


router = APIRouter(prefix="/auth/chat-sso", tags=["auth"], route_class=ChatSsoRoute)
BridgeHeader = Annotated[str | None, Header(alias="Authorization")]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.post("/approve", response_model=ApiResponse[ChatSsoApproveResponse])
async def approve(
    payload: ChatSsoApproveRequest,
    response: Response,
    token: TokenDep,
    current_user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[ChatSsoApproveResponse]:
    no_store(response)
    result = await ChatSsoService(session, settings).approve(
        token,
        current_user,
        payload.interaction_id,
    )
    return ApiResponse(data=ChatSsoApproveResponse(**result))


@router.post("/exchange", response_model=ApiResponse[ChatSsoExchangeResponse])
async def exchange(
    payload: ChatSsoExchangeRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    bridge_authorization: BridgeHeader = None,
) -> ApiResponse[ChatSsoExchangeResponse]:
    no_store(response)
    service = ChatSsoService(session, settings)
    service.require_bridge(bridge_authorization)
    result = await service.exchange(
        payload.client_id, payload.interaction_id, payload.approval_code
    )
    return ApiResponse(data=ChatSsoExchangeResponse(**result))


@router.post("/session-state", response_model=ApiResponse[ChatSsoStateResponse])
async def session_state(
    payload: ChatSsoStateRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    bridge_authorization: BridgeHeader = None,
) -> ApiResponse[ChatSsoStateResponse]:
    no_store(response)
    service = ChatSsoService(session, settings)
    service.require_bridge(bridge_authorization)
    result = await service.session_state(payload.client_id, payload.binding_id)
    return ApiResponse(data=ChatSsoStateResponse(**result))


@router.post("/revoke", response_model=ApiResponse[ChatSsoStateResponse])
async def revoke(
    payload: ChatSsoStateRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    bridge_authorization: BridgeHeader = None,
) -> ApiResponse[ChatSsoStateResponse]:
    no_store(response)
    service = ChatSsoService(session, settings)
    service.require_bridge(bridge_authorization)
    result = await service.revoke(payload.client_id, payload.binding_id)
    return ApiResponse(data=ChatSsoStateResponse(**result))
