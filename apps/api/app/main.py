from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.schemas.common import ErrorPayload, ErrorResponse

REQUEST_COUNT = 0
REQUEST_DURATION_SECONDS = 0.0
REQUEST_STATUS_COUNTS: dict[str, int] = {}


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

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
        request_id = request.headers.get("x-request-id", str(uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started_at = perf_counter()
        response = await call_next(request)
        duration_seconds = perf_counter() - started_at
        duration_ms = round(duration_seconds * 1000, 2)
        _record_request_metric(response.status_code, duration_seconds)
        response.headers["x-request-id"] = request_id
        structlog.get_logger("api.request").info(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        if duration_ms >= settings.slow_request_ms:
            structlog.get_logger("api.request").warning(
                "request_slow",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                threshold_ms=settings.slow_request_ms,
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
    async def root_healthz() -> dict[str, str]:
        return {"status": "ok", "service": "parallellines-api"}

    @app.get("/metrics", tags=["health"], response_class=PlainTextResponse)
    async def metrics() -> str:
        lines = [
            "# HELP parallellines_requests_total Total HTTP requests.",
            "# TYPE parallellines_requests_total counter",
            f"parallellines_requests_total {REQUEST_COUNT}",
            "# HELP parallellines_request_duration_seconds_total Total HTTP request duration.",
            "# TYPE parallellines_request_duration_seconds_total counter",
            f"parallellines_request_duration_seconds_total {REQUEST_DURATION_SECONDS:.6f}",
            "# HELP parallellines_requests_by_status_total Total HTTP requests by status code.",
            "# TYPE parallellines_requests_by_status_total counter",
        ]
        for status_code, count in sorted(REQUEST_STATUS_COUNTS.items()):
            lines.append(
                f'parallellines_requests_by_status_total{{status="{status_code}"}} {count}'
            )
        return "\n".join(lines) + "\n"

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


def _record_request_metric(status_code: int, duration_seconds: float) -> None:
    global REQUEST_COUNT, REQUEST_DURATION_SECONDS

    REQUEST_COUNT += 1
    REQUEST_DURATION_SECONDS += duration_seconds
    status_key = str(status_code)
    REQUEST_STATUS_COUNTS[status_key] = REQUEST_STATUS_COUNTS.get(status_key, 0) + 1


app = create_app()
