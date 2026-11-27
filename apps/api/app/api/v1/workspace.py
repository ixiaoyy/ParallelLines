import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.dependencies import SessionDep, SettingsDep, TokenDep
from app.core.exceptions import AppError
from app.schemas.common import ApiResponse, ErrorPayload, ErrorResponse
from app.schemas.workspace import (
    WorkspaceConfigSnapshot,
    WorkspaceConfigUpdate,
    parse_workspace_update,
)
from app.services.unified_auth import resolve_main_bearer_session
from app.services.workspace import WorkspaceConfigService

MAX_WORKSPACE_REQUEST_BYTES = 256 * 1024
WORKSPACE_BODY_TIMEOUT_SECONDS = 10
_LOGGER = structlog.get_logger(__name__)


class _PrivateWorkspaceRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        """只在工作台入口统一私有响应和安全错误，不修改全站异常处理。"""
        handler = super().get_route_handler()

        async def private_workspace(request: Request) -> Response:
            try:
                result = await handler(request)
            except AppError as exc:
                payload = ErrorResponse(
                    error=ErrorPayload(code=exc.code, message=exc.message, details=exc.details)
                )
                result = JSONResponse(status_code=exc.status_code, content=payload.model_dump())
            except HTTPException as exc:
                if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                    raise
                result = JSONResponse(
                    status_code=exc.status_code,
                    content=ErrorResponse(
                        error=ErrorPayload(code="authentication_required", message="请先登录主站")
                    ).model_dump(),
                    headers=exc.headers,
                )
            except SQLAlchemyError as exc:
                # SQL 异常可能带有配置绑定参数；日志仅记录错误类型。
                _LOGGER.error("workspace_storage_failed", error_type=type(exc).__name__)
                result = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content=ErrorResponse(
                        error=ErrorPayload(
                            code="workspace_storage_unavailable", message="暂时无法访问云配置"
                        )
                    ).model_dump(),
                )
            result.headers["Cache-Control"] = "private, no-store"
            if result.status_code == status.HTTP_401_UNAUTHORIZED:
                result.headers.setdefault("WWW-Authenticate", "Bearer")
            return result

        return private_workspace


router = APIRouter(prefix="/workspace", tags=["workspace"], route_class=_PrivateWorkspaceRoute)


async def _read_workspace_update(request: Request) -> WorkspaceConfigUpdate:
    """按实际接收字节限制 UTF-8 JSON；解析前不缓存超过上限的请求体。"""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    content_encoding = request.headers.get("content-encoding", "identity").strip().lower()
    if content_type != "application/json" or content_encoding != "identity":
        raise AppError("workspace_json_required", "仅支持未压缩的 UTF-8 JSON 请求", status_code=415)
    body = bytearray()
    try:
        async with asyncio.timeout(WORKSPACE_BODY_TIMEOUT_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_WORKSPACE_REQUEST_BYTES:
                    raise AppError(
                        "workspace_request_too_large", "同步请求最多 256 KiB", status_code=413
                    )
                body.extend(chunk)
    except TimeoutError:
        raise AppError("workspace_body_timeout", "读取同步请求超时", status_code=408) from None
    return parse_workspace_update(body)


@router.get(
    "/config",
    response_model=ApiResponse[WorkspaceConfigSnapshot],
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_workspace_config(
    session: SessionDep, settings: SettingsDep, token: TokenDep
) -> ApiResponse[WorkspaceConfigSnapshot]:
    """读取当前主站账号的云配置。首次使用时返回版本 0 和空配置。"""
    login = await resolve_main_bearer_session(session, settings, token)
    return ApiResponse(data=await WorkspaceConfigService(session).get(login.user.id))


@router.put(
    "/config",
    response_model=ApiResponse[WorkspaceConfigSnapshot],
    responses={
        201: {"model": ApiResponse[WorkspaceConfigSnapshot], "description": "首次创建云配置"},
        401: {"model": ErrorResponse},
        408: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "description": "仅包含支持同步的布局与偏好，不是本地完整导出。",
            "content": {"application/json": {"schema": WorkspaceConfigUpdate.model_json_schema()}},
        }
    },
)
async def put_workspace_config(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    token: TokenDep,
) -> ApiResponse[WorkspaceConfigSnapshot]:
    """原子保存当前账号的快照；客户端持有的基准版本过期时返回 409。"""
    # 先完成有界正文读取，避免慢客户端占用数据库事务。
    payload = await _read_workspace_update(request)
    login = await resolve_main_bearer_session(session, settings, token)
    snapshot = await WorkspaceConfigService(session).save(login.user.id, payload)
    if payload.expected_revision == "0":
        response.status_code = status.HTTP_201_CREATED
    return ApiResponse(data=snapshot)
