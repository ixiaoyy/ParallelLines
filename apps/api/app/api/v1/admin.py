from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.admin import (
    AdminBackgroundJobLogResponse,
    AdminBackgroundJobResponse,
    AdminEmailLogResponse,
    AdminSystemOverviewResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    SiteSettingResponse,
    SiteSettingUpdateRequest,
)
from app.schemas.common import ApiResponse
from app.schemas.moderation import AuditLogResponse
from app.services.admin import AdminService, SiteSettingService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=ApiResponse[list[SiteSettingResponse]])
async def list_site_settings(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[SiteSettingResponse]]:
    return ApiResponse(
        data=await SiteSettingService(session, settings).list_site_settings(current_user)
    )


@router.put("/settings/{key}", response_model=ApiResponse[SiteSettingResponse])
async def update_site_setting(
    key: str,
    payload: SiteSettingUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[SiteSettingResponse]:
    return ApiResponse(
        data=await SiteSettingService(session, settings).update_site_setting(
            key,
            payload,
            current_user,
        )
    )


@router.get("/users", response_model=ApiResponse[list[AdminUserResponse]])
async def list_users(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    role: str | None = None,
    user_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AdminUserResponse]]:
    users = await AdminService(session, settings).list_users(
        current_user,
        query=query,
        role=role,
        status=user_status,
        limit=limit,
    )
    return ApiResponse(data=users)


@router.get("/users/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def get_user(
    user_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminUserResponse]:
    return ApiResponse(data=await AdminService(session, settings).get_user(user_id, current_user))


@router.put("/users/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminUserResponse]:
    return ApiResponse(
        data=await AdminService(session, settings).update_user(user_id, payload, current_user)
    )


@router.get("/system", response_model=ApiResponse[AdminSystemOverviewResponse])
async def system_overview(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminSystemOverviewResponse]:
    return ApiResponse(data=await AdminService(session, settings).system_overview(current_user))


@router.get("/background-jobs", response_model=ApiResponse[list[AdminBackgroundJobResponse]])
async def list_background_jobs(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    job_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AdminBackgroundJobResponse]]:
    return ApiResponse(
        data=await AdminService(session, settings).list_background_jobs(
            current_user,
            status=job_status,
            limit=limit,
        )
    )


@router.get(
    "/background-jobs/{job_id}/logs",
    response_model=ApiResponse[list[AdminBackgroundJobLogResponse]],
)
async def list_background_job_logs(
    job_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[AdminBackgroundJobLogResponse]]:
    return ApiResponse(
        data=await AdminService(session, settings).list_background_job_logs(job_id, current_user)
    )


@router.get("/audit-logs", response_model=ApiResponse[list[AuditLogResponse]])
async def list_audit_logs(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AuditLogResponse]]:
    return ApiResponse(
        data=await AdminService(session, settings).list_audit_logs(current_user, limit=limit)
    )


@router.get("/email-logs", response_model=ApiResponse[list[AdminEmailLogResponse]])
async def list_email_logs(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AdminEmailLogResponse]]:
    return ApiResponse(
        data=AdminService(session, settings).email_logs(limit=limit, current_user=current_user)
    )
