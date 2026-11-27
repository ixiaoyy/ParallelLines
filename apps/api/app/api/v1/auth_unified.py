"""统一浏览器会话的固定 API 边界；旧登录和旧 Chat bearer 协议保持独立。"""

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.v1.dependencies import OptionalTokenDep, SessionDep, SettingsDep
from app.core.chat_sso import VerifiedLogin
from app.core.exceptions import AppError, AuthenticationError, PermissionDeniedError
from app.schemas.chat_sso import ChatSsoApproveRequest, ChatSsoApproveResponse
from app.schemas.common import ApiResponse
from app.schemas.unified_auth import (
    UnifiedAccessResponse,
    UnifiedAuthorizeRequest,
    UnifiedAuthorizeResponse,
    UnifiedBootstrapRequest,
    UnifiedExchangeRequest,
    UnifiedLogoutRequest,
    UnifiedLogoutResponse,
    UnifiedLogoutTicketRequest,
    UnifiedLogoutTicketResponse,
    UnifiedStateResponse,
)
from app.services.chat_sso import ChatSsoService
from app.services.unified_auth import UnifiedAuthService


class UnifiedRoute(APIRoute):
    def get_route_handler(self):
        """隐藏验证码/verifier/票据校验输入；包括失败响应在内均禁止缓存与 Referrer。"""

        handler = super().get_route_handler()

        async def protected(request: Request) -> Response:
            try:
                response = await handler(request)
            except RequestValidationError:
                response = JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "invalid_unified_request",
                            "message": "登录请求无效",
                            "details": {},
                        }
                    },
                )
            except AppError as error:
                response = JSONResponse(
                    status_code=error.status_code,
                    content={
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "details": error.details,
                        },
                    },
                )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        return protected


router = APIRouter(prefix="/auth/unified", tags=["auth"], route_class=UnifiedRoute)


@router.post("/bootstrap", response_model=ApiResponse[UnifiedAccessResponse])
async def bootstrap(
    payload: UnifiedBootstrapRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    token: OptionalTokenDep,
) -> ApiResponse[UnifiedAccessResponse]:
    """主站首次迁移或续发短 access；replace 仅用于用户显式完成登录后的身份切换。"""

    result = await UnifiedAuthService(session, settings).bootstrap(
        request,
        response,
        token,
        replace=payload.replace,
    )
    return ApiResponse(data=result)


@router.get("/state", response_model=ApiResponse[UnifiedStateResponse])
async def state(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[UnifiedStateResponse]:
    """供主站状态 iframe 读取最小身份状态；匿名也为 200，不返回任何凭据。"""

    service = UnifiedAuthService(session, settings)
    service.require_main_host(request)
    login = await service.cookie_login(request)
    return ApiResponse(data=service.state_for(login))


@router.post("/authorize", response_model=ApiResponse[UnifiedAuthorizeResponse])
async def authorize(
    payload: UnifiedAuthorizeRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[UnifiedAuthorizeResponse]:
    """仅在主站 Cookie 和 Origin 下给固定 Circle 回调发行 S256 单次授权码。"""

    return ApiResponse(data=await UnifiedAuthService(session, settings).authorize(request, payload))


@router.post("/exchange", response_model=ApiResponse[UnifiedAccessResponse])
async def exchange(
    payload: UnifiedExchangeRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[UnifiedAccessResponse]:
    """Circle 本域用 verifier 原子兑换短 JWT；不接受秘密、刷新令牌或自由客户端。"""

    return ApiResponse(data=await UnifiedAuthService(session, settings).exchange(request, payload))


@router.post("/logout-ticket", response_model=ApiResponse[UnifiedLogoutTicketResponse])
async def logout_ticket(
    payload: UnifiedLogoutTicketRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    token: OptionalTokenDep,
) -> ApiResponse[UnifiedLogoutTicketResponse]:
    """已登录 Main/Circle 只为自己的 sid 出票；用户随后到主站完成统一退出。"""

    service = UnifiedAuthService(session, settings)
    origin = request.headers.get("origin")
    if origin not in service.allowed_browser_origins():
        raise PermissionDeniedError("unified_origin_denied", "退出请求来源无效")
    service.require_origin(request, origin)
    if token is None:
        raise AuthenticationError("unified_login_required", "请先登录主站")
    login = await service.bearer_login(token, lock=True)
    return ApiResponse(data=await service.logout_ticket(login, payload.return_uri))


@router.post("/logout", response_model=ApiResponse[UnifiedLogoutResponse])
async def logout(
    payload: UnifiedLogoutRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[UnifiedLogoutResponse]:
    """主站完成单个浏览器 sid 的真实撤销；旧退出票据不能覆盖已经换号的新身份。"""

    return ApiResponse(
        data=await UnifiedAuthService(session, settings).logout(
            request,
            response,
            payload.ticket,
        )
    )


@router.post("/chat-approve", response_model=ApiResponse[ChatSsoApproveResponse])
async def chat_approve(
    payload: ChatSsoApproveRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[ChatSsoApproveResponse]:
    """中央 Cookie 自动审批现有 OIDC 交互；仍执行原 Chat 产品、会话和角色授权规则。"""

    service = UnifiedAuthService(session, settings)
    service.require_main_write(request)
    login = await service.cookie_login(request, lock=True)
    if login is None:
        raise AuthenticationError("unified_login_required", "请先登录主站")
    approval = await ChatSsoService(session, settings).approve_verified(
        VerifiedLogin(
            login.user.id,
            login.session.id,
            int(login.expires_at.timestamp()),
            unified_browser=True,
        ),
        payload.interaction_id,
    )
    return ApiResponse(data=ChatSsoApproveResponse(**approval))
