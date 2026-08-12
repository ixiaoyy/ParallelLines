from typing import Annotated

from fastapi import APIRouter, Query
from starlette.responses import FileResponse, Response

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
from app.schemas.backups import (
    BackupArtifactResponse,
    BackupCreateRequest,
    BackupRestoreRequest,
    BackupRestoreResponse,
)
from app.schemas.badges import BadgeGrantRequest, BadgeResponse, BadgeRevokeRequest
from app.schemas.common import ApiResponse
from app.schemas.moderation import AuditLogResponse
from app.schemas.news import (
    FrontierNewsCollectResponse,
    FrontierNewsItemQueueRequest,
    FrontierNewsItemResponse,
    FrontierNewsSourceCreateRequest,
    FrontierNewsSourceResponse,
    FrontierNewsSourceUpdateRequest,
)
from app.schemas.plugins import PluginResponse, PluginUpdateRequest
from app.schemas.privacy import PrivacyActionRequest, PrivacyActionResponse
from app.schemas.product_access import (
    FableSpaceAccessGrantUpdateRequest,
    FableSpaceAdminAccessRow,
)
from app.services.admin import AdminService, SiteSettingService
from app.services.backups import BackupService
from app.services.frontier_news import FrontierNewsService
from app.services.plugins import PluginService
from app.services.privacy import PrivacyService
from app.services.product_access import ProductAccessService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/fablespace/access-grants",
    response_model=ApiResponse[list[FableSpaceAdminAccessRow]],
)
async def list_fablespace_access_grants(
    session: SessionDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[FableSpaceAdminAccessRow]]:
    """List forum users, including ungranted users, for FableSpace access management."""

    rows = await ProductAccessService(session).list_fablespace_access_users(
        current_user,
        query=query,
        limit=limit,
    )
    return ApiResponse(data=rows)


@router.put(
    "/fablespace/access-grants/{user_id}",
    response_model=ApiResponse[FableSpaceAdminAccessRow],
)
async def grant_or_update_fablespace_access(
    user_id: str,
    payload: FableSpaceAccessGrantUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FableSpaceAdminAccessRow]:
    """Grant, update, or reactivate one user's independent FableSpace access."""

    row = await ProductAccessService(session).grant_or_update_fablespace_access(
        user_id,
        payload,
        current_user,
    )
    return ApiResponse(data=row)


@router.delete(
    "/fablespace/access-grants/{user_id}",
    response_model=ApiResponse[FableSpaceAdminAccessRow],
)
async def revoke_fablespace_access(
    user_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FableSpaceAdminAccessRow]:
    """Revoke one user's explicit FableSpace grant."""

    row = await ProductAccessService(session).revoke_fablespace_access(
        user_id,
        current_user,
    )
    return ApiResponse(data=row)


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
    updated = await SiteSettingService(session, settings).update_site_setting(
        key,
        payload,
        current_user,
    )
    if updated.public:
        from app.api.v1.site import invalidate_public_site_settings_cache

        invalidate_public_site_settings_cache()
    return ApiResponse(data=updated)


@router.get("/users", response_model=ApiResponse[list[AdminUserResponse]])
async def list_users(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    role: str | None = None,
    user_status: Annotated[str | None, Query(alias="status")] = None,
    is_persona: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[AdminUserResponse]]:
    users = await AdminService(session, settings).list_users(
        current_user,
        query=query,
        role=role,
        status=user_status,
        is_persona=is_persona,
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
    user = await AdminService(session, settings).update_user(user_id, payload, current_user)
    from app.api.seo import invalidate_sitemap_response_cache

    invalidate_sitemap_response_cache()
    return ApiResponse(data=user)


@router.post("/users/{user_id}/anonymize", response_model=ApiResponse[PrivacyActionResponse])
async def anonymize_user(
    user_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    payload: PrivacyActionRequest | None = None,
) -> ApiResponse[PrivacyActionResponse]:
    result = await PrivacyService(session, settings).anonymize_user(
        user_id,
        actor=current_user,
        reason=payload.reason if payload else None,
    )
    from app.api.seo import invalidate_sitemap_response_cache

    invalidate_sitemap_response_cache()
    return ApiResponse(data=result)


@router.delete("/users/{user_id}", response_model=ApiResponse[PrivacyActionResponse])
async def delete_user_account(
    user_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    payload: PrivacyActionRequest | None = None,
) -> ApiResponse[PrivacyActionResponse]:
    result = await PrivacyService(session, settings).delete_user(
        user_id,
        actor=current_user,
        reason=payload.reason if payload else None,
    )
    from app.api.seo import invalidate_sitemap_response_cache

    invalidate_sitemap_response_cache()
    return ApiResponse(data=result)


@router.get("/badges", response_model=ApiResponse[list[BadgeResponse]])
async def list_badges(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[BadgeResponse]]:
    return ApiResponse(data=await AdminService(session, settings).list_badges(current_user))


@router.get("/plugins", response_model=ApiResponse[list[PluginResponse]])
async def list_plugins(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[PluginResponse]]:
    return ApiResponse(data=await PluginService(session).list_plugins(current_user))


@router.put("/plugins/{plugin_id}", response_model=ApiResponse[PluginResponse])
async def update_plugin(
    plugin_id: str,
    payload: PluginUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PluginResponse]:
    updated = await PluginService(session).update_plugin(plugin_id, payload, current_user)

    from app.api.v1.site import invalidate_public_site_extensions_cache

    invalidate_public_site_extensions_cache()
    return ApiResponse(data=updated)


@router.post("/users/{user_id}/badges", response_model=ApiResponse[AdminUserResponse])
async def grant_user_badge(
    user_id: str,
    payload: BadgeGrantRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminUserResponse]:
    return ApiResponse(
        data=await AdminService(session, settings).grant_user_badge(
            user_id,
            badge_slug=payload.badge_slug,
            note=payload.note,
            current_user=current_user,
        )
    )


@router.post(
    "/users/{user_id}/badges/{badge_slug}/revoke",
    response_model=ApiResponse[AdminUserResponse],
)
async def revoke_user_badge(
    user_id: str,
    badge_slug: str,
    payload: BadgeRevokeRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminUserResponse]:
    return ApiResponse(
        data=await AdminService(session, settings).revoke_user_badge(
            user_id,
            badge_slug=badge_slug,
            reason=payload.reason,
            current_user=current_user,
        )
    )


@router.get("/system", response_model=ApiResponse[AdminSystemOverviewResponse])
async def system_overview(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminSystemOverviewResponse]:
    return ApiResponse(data=await AdminService(session, settings).system_overview(current_user))


@router.get(
    "/frontier-news/sources",
    response_model=ApiResponse[list[FrontierNewsSourceResponse]],
)
async def list_frontier_news_sources(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[FrontierNewsSourceResponse]]:
    """List white-listed sources used by the frontier news collector."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).list_sources(current_user)
    )


@router.post(
    "/frontier-news/sources",
    response_model=ApiResponse[FrontierNewsSourceResponse],
)
async def create_frontier_news_source(
    payload: FrontierNewsSourceCreateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsSourceResponse]:
    """Create a white-listed source for the frontier news collector."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).create_source(payload, current_user)
    )


@router.delete(
    "/frontier-news/sources/{source_id}",
    response_model=ApiResponse[FrontierNewsSourceResponse],
)
async def delete_frontier_news_source(
    source_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsSourceResponse]:
    """Remove one frontier source from admin lists and scheduled collection."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).delete_source(source_id, current_user)
    )


@router.put(
    "/frontier-news/sources/{source_id}",
    response_model=ApiResponse[FrontierNewsSourceResponse],
)
async def update_frontier_news_source(
    source_id: str,
    payload: FrontierNewsSourceUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsSourceResponse]:
    """Update source configuration, enabled state, or fetch cadence."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).update_source(
            source_id,
            payload,
            current_user,
        )
    )


@router.post(
    "/frontier-news/collect",
    response_model=ApiResponse[FrontierNewsCollectResponse],
)
async def collect_all_frontier_news(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsCollectResponse]:
    """Run a manual collection pass for all enabled frontier sources."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).collect_all_sources(current_user)
    )


@router.post(
    "/frontier-news/sources/{source_id}/collect",
    response_model=ApiResponse[FrontierNewsCollectResponse],
)
async def collect_frontier_news_source(
    source_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsCollectResponse]:
    """Run a manual collection pass for one frontier source."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).collect_source(source_id, current_user)
    )


@router.get(
    "/frontier-news/items",
    response_model=ApiResponse[list[FrontierNewsItemResponse]],
)
async def list_frontier_news_items(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    item_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[FrontierNewsItemResponse]]:
    """List collected frontier materials and their review/publication status."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).list_items(
            current_user,
            status=item_status,
            limit=limit,
        )
    )


@router.post(
    "/frontier-news/items/{item_id}/enrich",
    response_model=ApiResponse[FrontierNewsItemResponse],
)
async def enrich_frontier_news_item(
    item_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsItemResponse]:
    """Re-run AI整理 for one material and send it to the unified moderation queue."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).enrich_item(item_id, current_user)
    )


@router.post(
    "/frontier-news/items/{item_id}/queue",
    response_model=ApiResponse[FrontierNewsItemResponse],
)
async def queue_frontier_news_item(
    item_id: str,
    payload: FrontierNewsItemQueueRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[FrontierNewsItemResponse]:
    """Send one AI-prepared material to the existing reviewables queue."""

    return ApiResponse(
        data=await FrontierNewsService(session, settings).queue_item_for_review(
            item_id,
            current_user,
            note=payload.note,
        )
    )


@router.post("/backups", response_model=ApiResponse[BackupArtifactResponse])
async def create_backup(
    payload: BackupCreateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BackupArtifactResponse]:
    return ApiResponse(
        data=await BackupService(session, settings).create_site_backup(current_user, payload)
    )


@router.get("/backups", response_model=ApiResponse[list[BackupArtifactResponse]])
async def list_backups(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    backup_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[BackupArtifactResponse]]:
    return ApiResponse(
        data=await BackupService(session, settings).list_backups(
            current_user,
            status=backup_status,
            limit=limit,
        )
    )


@router.get("/backups/{backup_id}", response_model=ApiResponse[BackupArtifactResponse])
async def get_backup(
    backup_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BackupArtifactResponse]:
    return ApiResponse(
        data=await BackupService(session, settings).get_backup(backup_id, current_user)
    )


@router.get("/backups/{backup_id}/download")
async def download_backup(
    backup_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> FileResponse:
    backup_file = await BackupService(session, settings).backup_file(backup_id, current_user)
    return FileResponse(
        backup_file.path,
        media_type="application/zip",
        filename=backup_file.filename,
        headers={"X-Backup-SHA256": backup_file.sha256},
    )


@router.delete("/backups/{backup_id}", response_model=ApiResponse[BackupArtifactResponse])
async def delete_backup(
    backup_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BackupArtifactResponse]:
    return ApiResponse(
        data=await BackupService(session, settings).delete_backup(backup_id, current_user)
    )


@router.post("/backups/{backup_id}/restore", response_model=ApiResponse[BackupRestoreResponse])
async def validate_backup_restore(
    backup_id: str,
    payload: BackupRestoreRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BackupRestoreResponse]:
    return ApiResponse(
        data=await BackupService(session, settings).validate_restore(
            backup_id,
            payload,
            current_user,
        )
    )


@router.get("/exports/site")
async def export_site(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> Response:
    archive = await BackupService(session, settings).build_site_export(current_user)
    return Response(
        content=archive.content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.filename}"',
            "X-Export-SHA256": archive.sha256,
        },
    )


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
