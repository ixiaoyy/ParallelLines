"""阶段 2 独立账号服务试点入口（parallellines-account-api）。

严格边界：
1. 仅挂载账号、会话、SSO 与资料/邀请相关路由，不挂载游戏目录、圈子内容、审核或管理后台路由。
2. 启动时不执行 Alembic 迁移（数据库迁移保持唯一执行责任方）。
3. 提供真实数据库连通性探针 /readyz，区分进程存活（/healthz）与可承接流量（/readyz）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from secrets import token_hex
from time import perf_counter

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import auth, auth_chat_sso, auth_unified
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.schemas.common import ErrorPayload, ErrorResponse

SERVICE_NAME = "parallellines-account-api"


def create_account_router() -> APIRouter:
    """只聚合窄账号认证与 SSO 边界路由，不挂载 /users、/invites 及任何业务路由。"""
    router = APIRouter()
    router.include_router(auth.router)
    router.include_router(auth_chat_sso.router)
    router.include_router(auth_unified.router)
    return router


def create_account_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} Account Service",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ):
        request_id = request.headers.get("x-request-id", token_hex(16))
        structlog.contextvars.bind_contextvars(request_id=request_id, service=SERVICE_NAME)
        started_at = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers["x-request-id"] = request_id
        structlog.get_logger("account.request").info(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorPayload(code=exc.code, message=exc.message, details=exc.details)
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorPayload(
                code="validation_error",
                message="Request validation failed",
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.get("/healthz", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME}

    @app.get("/readyz", tags=["health"])
    async def readiness() -> JSONResponse:
        """核对数据库真实可查询，作为网关切流前的就绪门槛。"""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "service": SERVICE_NAME},
            )
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "service": SERVICE_NAME},
        )

    app.include_router(create_account_router(), prefix=settings.api_v1_prefix)
    return app


app = create_account_app()
