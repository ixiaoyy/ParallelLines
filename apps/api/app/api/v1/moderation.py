from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.moderation import (
    AuditLogResponse,
    FlagCreateRequest,
    FlagResponse,
    FlagStatus,
    FlagStatusUpdateRequest,
    HideContentRequest,
    ModerationActionResponse,
    ScreenedRuleCreateRequest,
    ScreenedRuleKind,
    ScreenedRuleResponse,
    SpamActionResponse,
    UserStatusResponse,
    UserStatusUpdateRequest,
)
from app.services.moderation import ModerationService
from app.services.spam import SpamPreventionService

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.post(
    "/flags",
    response_model=ApiResponse[FlagResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_flag(
    payload: FlagCreateRequest,
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FlagResponse]:
    flag = await ModerationService(session).create_flag(payload, current_user, request)
    return ApiResponse(data=flag)


@router.get("/queue", response_model=ApiResponse[list[FlagResponse]])
async def list_moderation_queue(
    session: SessionDep,
    current_user: CurrentUserDep,
    flag_status: Annotated[FlagStatus | None, Query(alias="status")] = "pending",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[FlagResponse]]:
    flags = await ModerationService(session).list_flags(
        current_user,
        status=flag_status,
        limit=limit,
    )
    return ApiResponse(data=flags)


@router.put("/flags/{flag_id}/status", response_model=ApiResponse[FlagResponse])
async def update_flag_status(
    flag_id: str,
    payload: FlagStatusUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FlagResponse]:
    flag = await ModerationService(session).update_flag_status(flag_id, payload, current_user)
    return ApiResponse(data=flag)


@router.put("/topics/{topic_id}/hide", response_model=ApiResponse[ModerationActionResponse])
async def hide_topic(
    topic_id: str,
    payload: HideContentRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ModerationActionResponse]:
    result = await ModerationService(session).hide_topic(topic_id, payload, current_user)
    return ApiResponse(data=result)


@router.put("/topics/{topic_id}/restore", response_model=ApiResponse[ModerationActionResponse])
async def restore_topic(
    topic_id: str,
    payload: HideContentRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ModerationActionResponse]:
    result = await ModerationService(session).restore_topic(topic_id, payload, current_user)
    return ApiResponse(data=result)


@router.put("/posts/{post_id}/hide", response_model=ApiResponse[ModerationActionResponse])
async def hide_post(
    post_id: str,
    payload: HideContentRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ModerationActionResponse]:
    result = await ModerationService(session).hide_post(post_id, payload, current_user)
    return ApiResponse(data=result)


@router.put("/posts/{post_id}/restore", response_model=ApiResponse[ModerationActionResponse])
async def restore_post(
    post_id: str,
    payload: HideContentRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ModerationActionResponse]:
    result = await ModerationService(session).restore_post(post_id, payload, current_user)
    return ApiResponse(data=result)


@router.put("/users/{user_id}/status", response_model=ApiResponse[UserStatusResponse])
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserStatusResponse]:
    result = await ModerationService(session).update_user_status(user_id, payload, current_user)
    return ApiResponse(data=result)


@router.get("/audit-logs", response_model=ApiResponse[list[AuditLogResponse]])
async def list_audit_logs(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AuditLogResponse]]:
    logs = await ModerationService(session).list_audit_logs(current_user, limit=limit)
    return ApiResponse(data=logs)


@router.get("/screened-rules", response_model=ApiResponse[list[ScreenedRuleResponse]])
async def list_screened_rules(
    session: SessionDep,
    current_user: CurrentUserDep,
    kind: ScreenedRuleKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ApiResponse[list[ScreenedRuleResponse]]:
    rules = await SpamPreventionService(session).list_screened_rules(
        current_user,
        kind=kind,
        limit=limit,
    )
    return ApiResponse(data=rules)


@router.post(
    "/screened-rules",
    response_model=ApiResponse[ScreenedRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_screened_rule(
    payload: ScreenedRuleCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ScreenedRuleResponse]:
    rule = await SpamPreventionService(session).create_screened_rule(payload, current_user)
    return ApiResponse(data=rule)


@router.delete("/screened-rules/{rule_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_screened_rule(
    rule_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[dict[str, bool]]:
    await SpamPreventionService(session).delete_screened_rule(rule_id, current_user)
    return ApiResponse(data={"ok": True})


@router.get("/spam-actions", response_model=ApiResponse[list[SpamActionResponse]])
async def list_spam_actions(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ApiResponse[list[SpamActionResponse]]:
    actions = await SpamPreventionService(session).list_spam_actions(
        current_user,
        limit=limit,
    )
    return ApiResponse(data=actions)
