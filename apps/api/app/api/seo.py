from __future__ import annotations

from fastapi import APIRouter, Query, Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from app.api.v1.dependencies import SessionDep
from app.schemas.common import ApiResponse
from app.schemas.seo import SeoMetaResponse
from app.services.seo import SeoService

public_seo_router = APIRouter(tags=["seo"])
api_seo_router = APIRouter(prefix="/seo", tags=["seo"])


@public_seo_router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(request: Request, session: SessionDep) -> Response:
    service = SeoService(session)
    xml = service.build_sitemap_xml(await service.sitemap_urls(base_url(request)))
    return Response(content=xml, media_type="application/xml; charset=utf-8")


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
