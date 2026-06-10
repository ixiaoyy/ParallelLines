from __future__ import annotations

from fastapi import APIRouter, Query, Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from app.api.v1.dependencies import SessionDep
from app.core.response_cache import ResponseHotCache
from app.schemas.common import ApiResponse
from app.schemas.seo import SeoMetaResponse
from app.services.seo import SeoService

public_seo_router = APIRouter(tags=["seo"])
api_seo_router = APIRouter(prefix="/seo", tags=["seo"])

SITEMAP_CACHE_TTL_SECONDS = 3600

_SITEMAP_XML_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=SITEMAP_CACHE_TTL_SECONDS,
    max_entries=16,
)


# Clear cached XML when public content visibility or canonical paths change.
def invalidate_sitemap_response_cache() -> None:
    """Clear cached sitemap XML responses after public content writes.

    There are no parameters and no return value. Side effect: invalidates this
    process' `/sitemap.xml` hot-cache entries so removed private/hidden content
    cannot persist until the sitemap TTL expires.
    """

    _SITEMAP_XML_RESPONSE_CACHE.clear()


@public_seo_router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(request: Request, session: SessionDep) -> Response:
    cache_key = base_url(request)
    cache_control = (
        f"public, max-age={SITEMAP_CACHE_TTL_SECONDS}, "
        f"stale-while-revalidate={SITEMAP_CACHE_TTL_SECONDS}"
    )
    cached_xml = _SITEMAP_XML_RESPONSE_CACHE.get(cache_key)
    if cached_xml is not None:
        return Response(
            content=cached_xml,
            media_type="application/xml; charset=utf-8",
            headers={
                "Cache-Control": cache_control,
                "X-ParallelLines-Cache": "hit",
            },
        )

    service = SeoService(session)
    xml = service.build_sitemap_xml(await service.sitemap_urls(cache_key))
    _SITEMAP_XML_RESPONSE_CACHE.set(cache_key, xml)
    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={
            "Cache-Control": cache_control,
            "X-ParallelLines-Cache": "miss",
        },
    )


@public_seo_router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request, session: SessionDep) -> PlainTextResponse:
    content = await SeoService(session).robots_txt(base_url(request))
    return PlainTextResponse(content=content)


@public_seo_router.get("/t/{legacy_slug}/{topic_id}")
async def legacy_topic_redirect(
    legacy_slug: str,
    topic_id: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    _ = legacy_slug
    redirect = await SeoService(session).legacy_topic_redirect(topic_id, base_url(request))
    return RedirectResponse(url=redirect.location, status_code=redirect.status_code)


@public_seo_router.get("/p/{topic_id}")
async def compact_topic_redirect(
    topic_id: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    redirect = await SeoService(session).legacy_topic_redirect(topic_id, base_url(request))
    return RedirectResponse(url=redirect.location, status_code=redirect.status_code)


@api_seo_router.get("/meta", response_model=ApiResponse[SeoMetaResponse])
async def seo_meta(
    request: Request,
    session: SessionDep,
    path: str = Query(default="/"),
) -> ApiResponse[SeoMetaResponse]:
    meta = await SeoService(session).meta_for_path(path, base_url(request))
    return ApiResponse(data=meta)


def base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")
