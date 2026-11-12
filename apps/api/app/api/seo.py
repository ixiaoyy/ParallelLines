from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit

from fastapi import APIRouter, Query, Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from app.api.v1.dependencies import SessionDep
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.response_cache import ResponseHotCache
from app.schemas.common import ApiResponse
from app.schemas.seo import SeoMetaResponse
from app.services.seo import LegacyTopicRedirect, SeoPageDocument, SeoService, normalize_path
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
    forum = is_forum_request(request)
    origin = forum_base_url(request) if forum else base_url(request)
    # 两站独立缓存，避免论坛公开索引与游戏目录相互覆盖。
    cache_key = f"forum:{origin}" if forum else origin
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
    urls = await service.forum_sitemap_urls(origin) if forum else await service.sitemap_urls(origin)
    xml = service.build_sitemap_xml(urls)
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
    origin = forum_base_url(request) if is_forum_request(request) else base_url(request)
    content = await SeoService(session).robots_txt(origin)
    return PlainTextResponse(content=content)


@public_seo_router.get("/t/{legacy_slug}/{topic_id}")
async def legacy_topic_redirect(
    legacy_slug: str,
    topic_id: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    _ = legacy_slug
    redirect = await SeoService(session).legacy_topic_redirect(topic_id, forum_base_url(request))
    return RedirectResponse(url=redirect.location, status_code=redirect.status_code)


@public_seo_router.get("/p/{topic_id}")
async def compact_topic_redirect(
    topic_id: str,
    request: Request,
    session: SessionDep,
) -> RedirectResponse:
    redirect = await SeoService(session).legacy_topic_redirect(topic_id, forum_base_url(request))
    return RedirectResponse(url=redirect.location, status_code=redirect.status_code)


@api_seo_router.get("/meta", response_model=ApiResponse[SeoMetaResponse])
async def seo_meta(
    request: Request,
    session: SessionDep,
    path: str = Query(default="/"),
) -> ApiResponse[SeoMetaResponse]:
    settings = get_settings()
    normalized = normalize_path(path)
    forum = is_forum_request(request, settings)
    forum_path = normalized in {"/forum", "/boards"} or normalized.startswith(
        ("/b/", "/topics/", "/members/", "/t/", "/p/")
    )
    # 仅论坛内容使用固定论坛来源；请求头不能注入任意规范地址。
    forum_target = forum_path or (forum and normalized == "/")
    origin = forum_base_url(request, settings) if forum_target else base_url(request)
    if settings.public_forum_url is not None and forum_target:
        meta = await SeoService(session).meta_for_path(path, origin, forum_home=True)
    else:
        meta = await SeoService(session).meta_for_path(path, origin)
    return ApiResponse(data=meta)


@public_seo_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_page(request: Request, session: SessionDep) -> Response:
    """按已配置来源返回论坛或游戏根页；只读公开内容，不改计数、链接或账号状态。"""

    if is_forum_request(request):
        # 独立论坛仅接管其已配置来源的根页，主域目录首页保持原行为。
        document = await SeoService(session).forum_page(forum_base_url(request), canonical_path="/")
    else:
        document = await SeoService(session).home_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/games", response_class=HTMLResponse, include_in_schema=False)
async def games_page(request: Request, session: SessionDep) -> Response:
    """Return the game directory at the compatible games URL without redirecting.

    ``request`` resolves the canonical origin and ``session`` reads the same
    public catalog. The response does not record views or change game links.
    """

    document = await SeoService(session).home_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get(
    "/play/generals-soldiers", response_class=HTMLResponse, include_in_schema=False
)
@public_seo_router.get("/play/snake-escape", response_class=HTMLResponse, include_in_schema=False)
@public_seo_router.get("/play/flappy-dunk", response_class=HTMLResponse, include_in_schema=False)
async def game_page(request: Request, session: SessionDep) -> Response:
    """返回三款已开放游戏的语义首屏，保留原应用接管与游戏入口。

    ``request`` 选择已登记路径及规范域名，``session`` 只读站点品牌；响应不启动游戏或写计数。
    """

    document = await SeoService(session).game_page(request.url.path, base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/tools", response_class=HTMLResponse, include_in_schema=False)
async def tools_page(request: Request, session: SessionDep) -> Response:
    """Return the tools landing page with its current empty state.

    ``request`` resolves the canonical origin and ``session`` reads site
    branding. No tool capabilities, permissions, or content are created.
    """

    document = await SeoService(session).tools_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/forum", response_class=HTMLResponse, include_in_schema=False)
async def forum_page(request: Request, session: SessionDep) -> Response:
    """独立论坛启用后规范跳转到其根页；未启用时保留原论坛公开语义文档。

    ``request`` 的查询串仅随固定目标保留；``session`` 仅在旧模式读取公开内容，
    不写计数、账号或权限，也不改变目录首页。
    """

    settings = get_settings()
    if settings.public_forum_url is not None:
        # 已启用独立论坛时归一化旧入口；原始查询串保留，片段由浏览器继承。
        suffix = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"{settings.public_forum_url}/{suffix}", status_code=301)
    document = await SeoService(session).forum_page(base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/boards", response_class=HTMLResponse, include_in_schema=False)
async def boards_page(request: Request, session: SessionDep) -> Response:
    """Return the canonical semantic public-board directory in the SPA shell.

    ``request`` and ``session`` resolve canonical configuration and public board
    data. The read-only response is excluded from OpenAPI.
    """

    document = await SeoService(session).boards_page(forum_base_url(request))
    return await html_page_response(document)


@public_seo_router.get("/b/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def board_page(slug: str, request: Request, session: SessionDep) -> Response:
    """Return a public, restricted, or missing board document for decoded ``slug``.

    ``request`` supplies canonical origin fallback and ``session`` classifies
    anonymous visibility. The response preserves real 404/noindex semantics.
    """

    document = await SeoService(session).board_page(slug, forum_base_url(request))
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

    resolution = await SeoService(session).topic_page(topic_id, slug, forum_base_url(request))
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

    resolution = await SeoService(session).topic_page(topic_id, None, forum_base_url(request))
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

    document = await SeoService(session).profile_page(user_id, forum_base_url(request))
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
    if (
        settings.public_forum_url is not None
        and urlsplit(document.meta.canonical_url).netloc.lower()
        == urlsplit(settings.public_forum_url).netloc.lower()
    ):
        # 论坛必须使用独立构建外壳，缺配置明确失败，不静默加载主站目录应用。
        shell_url = settings.forum_web_app_shell_url
        document = replace(document, home_path="/")
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


def forum_base_url(request: Request, settings: Settings | None = None) -> str:
    """返回配置的论坛规范来源；未配置时完整沿用旧主站来源规则，无副作用。"""

    settings = settings or get_settings()
    return settings.public_forum_url or base_url(request, settings)


def is_forum_request(request: Request, settings: Settings | None = None) -> bool:
    """仅将与已配置论坛主机匹配的请求识别为论坛；不采信转发头选择任意来源。"""

    configured = (settings or get_settings()).public_forum_url
    if configured is None:
        return False
    expected = urlsplit(configured)
    # TLS 可在受信反代终结，比较主机及显式端口，不用代理内层 HTTP 协议判断站点。
    return request.url.netloc.lower() == expected.netloc.lower()
