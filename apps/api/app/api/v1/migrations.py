from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.migrations import (
    MigrationExportResponse,
    MigrationImportRequest,
    MigrationImportResponse,
)
from app.services.migrations import MigrationService

router = APIRouter(prefix="/admin/migrations", tags=["admin"])


@router.post("/import/preview", response_model=ApiResponse[MigrationImportResponse])
async def preview_migration_import(
    payload: MigrationImportRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[MigrationImportResponse]:
    return ApiResponse(data=await MigrationService(session).preview_import(payload, current_user))


@router.post("/import/run", response_model=ApiResponse[MigrationImportResponse])
async def run_migration_import(
    payload: MigrationImportRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[MigrationImportResponse]:
    """Return the committed import result and refresh affected public read caches.

    Payload contains validated records and current_user supplies the existing
    admin gate. Preview imports do not enter this path or invalidate caches.
    """

    result = await MigrationService(session).run_import(payload, current_user)
    if result.created or result.updated:
        from app.api.v1.topics import invalidate_topic_write_response_caches

        invalidate_topic_write_response_caches()
    return ApiResponse(data=result)


@router.get("/export", response_model=ApiResponse[MigrationExportResponse])
async def export_migration_json(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[MigrationExportResponse]:
    return ApiResponse(data=await MigrationService(session).export_site(current_user))
