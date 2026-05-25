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
    return ApiResponse(data=await MigrationService(session).run_import(payload, current_user))


@router.get("/export", response_model=ApiResponse[MigrationExportResponse])
async def export_migration_json(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[MigrationExportResponse]:
    return ApiResponse(data=await MigrationService(session).export_site(current_user))
