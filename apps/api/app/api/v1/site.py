from fastapi import APIRouter

from app.api.v1.dependencies import SessionDep, SettingsDep
from app.schemas.admin import PublicSiteSettingsResponse
from app.schemas.common import ApiResponse
from app.services.admin import SiteSettingService

router = APIRouter(prefix="/site", tags=["site"])


@router.get("/settings", response_model=ApiResponse[PublicSiteSettingsResponse])
async def public_site_settings(
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[PublicSiteSettingsResponse]:
    return ApiResponse(data=await SiteSettingService(session, settings).public_site_settings())
