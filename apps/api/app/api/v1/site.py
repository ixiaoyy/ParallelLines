from fastapi import APIRouter, Response

from app.api.v1.dependencies import SessionDep, SettingsDep
from app.core.response_cache import ResponseHotCache
from app.schemas.admin import PublicSiteSettingsResponse
from app.schemas.common import ApiResponse
from app.schemas.plugins import PluginUiExtensionResponse
from app.services.admin import SiteSettingService
from app.services.plugins import PluginService

router = APIRouter(prefix="/site", tags=["site"])

PUBLIC_SITE_SETTINGS_CACHE_TTL_SECONDS = 60
PUBLIC_SITE_EXTENSIONS_CACHE_TTL_SECONDS = 120

_PUBLIC_SITE_SETTINGS_RESPONSE_CACHE = ResponseHotCache[ApiResponse[PublicSiteSettingsResponse]](
    ttl_seconds=PUBLIC_SITE_SETTINGS_CACHE_TTL_SECONDS,
    max_entries=8,
)
_PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE = ResponseHotCache[
    ApiResponse[list[PluginUiExtensionResponse]]
](
    ttl_seconds=PUBLIC_SITE_EXTENSIONS_CACHE_TTL_SECONDS,
    max_entries=8,
)


@router.get("/settings", response_model=ApiResponse[PublicSiteSettingsResponse])
async def public_site_settings(
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
) -> ApiResponse[PublicSiteSettingsResponse]:
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    cached = _PUBLIC_SITE_SETTINGS_RESPONSE_CACHE.get("public")
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return cached

    payload = ApiResponse(data=await SiteSettingService(session, settings).public_site_settings())
    _PUBLIC_SITE_SETTINGS_RESPONSE_CACHE.set("public", payload)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return payload


@router.get("/extensions", response_model=ApiResponse[list[PluginUiExtensionResponse]])
async def public_site_extensions(
    session: SessionDep,
    response: Response,
) -> ApiResponse[list[PluginUiExtensionResponse]]:
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    cached = _PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE.get("public")
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return cached

    payload = ApiResponse(data=await PluginService(session).public_ui_extensions())
    _PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE.set("public", payload)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return payload
