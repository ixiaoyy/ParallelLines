from fastapi import APIRouter, Request, Response, status

from app.api.v1.dependencies import OptionalCurrentUserDep, SessionDep, SettingsDep
from app.core.response_cache import ResponseHotCache, cached_json_response
from app.schemas.admin import PublicSiteSettingsResponse
from app.schemas.analytics import SiteVisitCreateRequest, SiteVisitRecordResponse
from app.schemas.common import ApiResponse
from app.schemas.plugins import PluginUiExtensionResponse
from app.services.admin import SiteSettingService
from app.services.plugins import PluginService
from app.services.site_visits import SiteVisitService

router = APIRouter(prefix="/site", tags=["site"])

PUBLIC_SITE_SETTINGS_CACHE_TTL_SECONDS = 60
PUBLIC_SITE_EXTENSIONS_CACHE_TTL_SECONDS = 120

_PUBLIC_SITE_SETTINGS_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=PUBLIC_SITE_SETTINGS_CACHE_TTL_SECONDS,
    max_entries=8,
)
_PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=PUBLIC_SITE_EXTENSIONS_CACHE_TTL_SECONDS,
    max_entries=8,
)


def invalidate_public_site_settings_cache() -> None:
    """Invalidate public site settings after an admin setting change."""

    _PUBLIC_SITE_SETTINGS_RESPONSE_CACHE.clear()


def invalidate_public_site_extensions_cache() -> None:
    """Invalidate public UI extension responses after plugin configuration changes."""

    _PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE.clear()


@router.get("/settings", response_model=ApiResponse[PublicSiteSettingsResponse])
async def public_site_settings(
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
) -> Response:
    cache_control = "public, max-age=60, stale-while-revalidate=300"
    cached_json = _PUBLIC_SITE_SETTINGS_RESPONSE_CACHE.get("public")
    if cached_json is not None:
        return cached_json_response(
            cached_json,
            cache_control=cache_control,
            cache_status="hit",
        )

    payload = ApiResponse(data=await SiteSettingService(session, settings).public_site_settings())
    json_content = payload.model_dump_json()
    _PUBLIC_SITE_SETTINGS_RESPONSE_CACHE.set("public", json_content)
    return cached_json_response(
        json_content,
        cache_control=cache_control,
        cache_status="miss",
    )


@router.get("/extensions", response_model=ApiResponse[list[PluginUiExtensionResponse]])
async def public_site_extensions(
    session: SessionDep,
    response: Response,
) -> Response:
    cache_control = "public, max-age=120, stale-while-revalidate=300"
    cached_json = _PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE.get("public")
    if cached_json is not None:
        return cached_json_response(
            cached_json,
            cache_control=cache_control,
            cache_status="hit",
        )

    payload = ApiResponse(data=await PluginService(session).public_ui_extensions())
    json_content = payload.model_dump_json()
    _PUBLIC_SITE_EXTENSIONS_RESPONSE_CACHE.set("public", json_content)
    return cached_json_response(
        json_content,
        cache_control=cache_control,
        cache_status="miss",
    )


@router.post(
    "/visits",
    response_model=ApiResponse[SiteVisitRecordResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def record_site_visit(
    payload: SiteVisitCreateRequest,
    request: Request,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[SiteVisitRecordResponse]:
    """Record a public page-view event for site traffic analytics.

    Key parameters are the browser payload, visitor header, optional user, and
    request origin/host. Return value confirms whether the event was accepted.
    Side effect: writes one `site_visits` row when the visitor identity is valid.
    """

    data = await SiteVisitService(session).record_visit(
        payload,
        visitor_id=request.headers.get("X-ParallelLines-Visitor"),
        current_user=current_user,
        origin=request.headers.get("origin"),
        request_host=request.url.hostname,
        user_agent=request.headers.get("user-agent"),
    )
    return ApiResponse(data=data)
