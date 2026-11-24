from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, Request, Response, status
from pydantic import ValidationError as PayloadValidationError

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.core.exceptions import AppError, ValidationError
from app.schemas.common import ApiResponse
from app.schemas.traffic import (
    TrafficAcceptedResponse,
    TrafficBatchRequest,
    TrafficOverviewResponse,
    TrafficSelection,
)
from app.services.traffic_queue import TrafficQueue, normalize_traffic_batch

router = APIRouter(prefix="/site", tags=["site"])
admin_router = APIRouter(prefix="/admin/analytics", tags=["admin"])
MAX_TRAFFIC_BODY_BYTES = 16 * 1024


@router.post(
    "/traffic",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[TrafficAcceptedResponse],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/plain": {"schema": {"type": "string", "maxLength": 16384}}},
            "description": "JSON-encoded TrafficBatchRequest, no credentials or private content.",
        }
    },
)
async def collect_traffic(
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> ApiResponse[TrafficAcceptedResponse]:
    """接收匿名小批次并入 Redis 队列；无业务会话或 SQL 依赖，失败不走同步入库兜底。"""

    if not settings.traffic_enabled:
        raise AppError("traffic_disabled", "跨站统计尚未启用", status_code=503)
    if request.headers.get("dnt") == "1" or request.headers.get("sec-gpc") == "1":
        return ApiResponse(data=TrafficAcceptedResponse(accepted=0))
    body = bytearray()
    try:
        async with asyncio.timeout(1):
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_TRAFFIC_BODY_BYTES:
                    raise AppError("traffic_batch_too_large", "统计批次过大", status_code=413)
    except TimeoutError as exc:
        raise AppError("traffic_body_timeout", "统计请求超时", status_code=408) from exc
    try:
        payload = TrafficBatchRequest.model_validate_json(body)
    except PayloadValidationError as exc:
        # 不回传可能包含私密 URL 的原始校验输入。
        raise ValidationError("traffic_batch_invalid", "统计批次格式无效") from exc
    origin, events = normalize_traffic_batch(
        payload,
        origin=request.headers.get("origin"),
        user_agent=request.headers.get("user-agent"),
        settings=settings,
    )
    accepted = await TrafficQueue(settings).enqueue(events)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    return ApiResponse(data=TrafficAcceptedResponse(accepted=accepted))


@admin_router.get("/traffic", response_model=ApiResponse[TrafficOverviewResponse])
async def traffic_overview(
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
    response: Response,
    start_date: date | None = None,
    end_date: date | None = None,
    site_key: TrafficSelection = "all",
) -> ApiResponse[TrafficOverviewResponse]:
    """管理员读取五分钟缓存的流量报表；查询只针对独立统计表，旧分析接口保持不变。"""

    from app.services.traffic import TrafficService

    response.headers["Cache-Control"] = "private, no-store"
    return ApiResponse(
        data=await TrafficService(session, settings).overview(
            current_user, start_date=start_date, end_date=end_date, site_key=site_key
        )
    )
