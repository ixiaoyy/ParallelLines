from __future__ import annotations

from fastapi import APIRouter, Query, Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from app.api.v1.dependencies import SessionDep
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.response_cache import ResponseHotCache
from app.schemas.common import ApiResponse
from app.schemas.seo import SeoMetaResponse
from app.services.seo import LegacyTopicRedirect, SeoPageDocument, SeoService
from app.services.seo_renderer import load_app_shell, render_seo_document

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


@public_seo_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_page(request: Request, session: SessionDep) -> Response:
    """Return the canonical semantic home document inside the compiled SPA shell.

    ``request`` provides a local/test fallback origin and ``session`` reads public
    content. The response never records views and is excluded from OpenAPI.
    """

    document = await SeoService(session).home_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/boards", response_class=HTMLResponse, include_in_schema=False)
async def boards_page(request: Request, session: SessionDep) -> Response:
    """Return the canonical semantic public-board directory in the SPA shell.

    ``request`` and ``session`` resolve canonical configuration and public board
    data. The read-only response is excluded from OpenAPI.
    """

    document = await SeoService(session).boards_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/b/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def board_page(slug: str, request: Request, session: SessionDep) -> Response:
    """Return a public, restricted, or missing board document for decoded ``slug``.

    ``request`` supplies canonical origin fallback and ``session`` classifies
    anonymous visibility. The response preserves real 404/noindex semantics.
    """

    document = await SeoService(session).board_page(slug, base_url(request))
    return await html_page_response(document)


@public_seo_router.get(
    "/topics/{topic_id}/{slug}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def topic_page_with_slug(
    topic_id: str,
    slug: str,
    request: Request,
    session: SessionDep,
) -> Response:
    """Return or permanently normalize a topic route containing ``slug``.

    ``topic_id`` and decoded ``slug`` identify the requested topic while request
    configuration supplies the canonical origin. Public content is read without
    incrementing views; redirects and real error states are preserved.
    """

    resolution = await SeoService(session).topic_page(topic_id, slug, base_url(request))
    return await topic_page_response(resolution)


@public_seo_router.get(
    "/topics/{topic_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def topic_page_without_slug(
    topic_id: str,
    request: Request,
    session: SessionDep,
) -> Response:
    """Permanently normalize a public slugless topic URL or return a safe shell.

    ``topic_id`` selects the topic and ``request`` supplies canonical origin
    fallback. Public topics redirect to their slugged URL; restricted/missing
    states retain the designed noindex/404 behavior without counter writes.
    """

    resolution = await SeoService(session).topic_page(topic_id, None, base_url(request))
    return await topic_page_response(resolution)


@public_seo_router.get(
    "/members/{user_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def profile_page(user_id: str, request: Request, session: SessionDep) -> Response:
    """Return a public, restricted, or missing member-profile SPA document.

    ``user_id`` is the stable profile key, while ``request`` and ``session``
    provide canonical origin and anonymous visibility. No private fields are
    emitted into the initial HTML.
    """

    document = await SeoService(session).profile_page(user_id, base_url(request))
    return await html_page_response(document)


async def topic_page_response(resolution: SeoPageDocument | LegacyTopicRedirect) -> Response:
    """Convert a typed topic ``resolution`` into an HTML or permanent redirect response.

    Redirects are returned untouched; documents are rendered through the shared
    compiled shell. The function performs only response construction/network
    shell loading and preserves the service-selected status code.
    """

    if isinstance(resolution, LegacyTopicRedirect):
        return RedirectResponse(url=resolution.location, status_code=resolution.status_code)
    return await html_page_response(resolution)


async def html_page_response(document: SeoPageDocument) -> HTMLResponse:
    """Render typed SEO ``document`` into the trusted compiled Web application shell.

    The shell URL comes only from settings. The returned HTML uses no-cache and
    emits an initial X-Robots-Tag for non-indexable documents; missing config or
    shell failures raise a typed 503 for Nginx fallback handling.
    """

    settings = get_settings()
    shell_url = settings.web_app_shell_url
    if shell_url is None:
        raise AppError(
            "seo_shell_not_configured",
            "Compiled Web shell URL is not configured",
            status_code=503,
        )
    rendered = render_seo_document(
        await load_app_shell(shell_url),
        document,
        baidu_site_verification=settings.baidu_site_verification,
    )
    headers = {"Cache-Control": "no-cache"}
    if document.meta.robots != "index,follow":
        headers["X-Robots-Tag"] = document.meta.robots.replace(",", ", ")
    return HTMLResponse(
        content=rendered,
        status_code=document.status_code,
        headers=headers,
    )


def base_url(request: Request, settings: Settings | None = None) -> str:
    """Return the configured canonical origin or a local/test request fallback.

    ``request`` is consulted only when ``settings.public_site_url`` is unset.
    Forwarded headers are never parsed here, so a configured production origin
    cannot be changed by request headers. The function has no side effects.
    """

    configured = (settings or get_settings()).public_site_url
    if configured is not None:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")
