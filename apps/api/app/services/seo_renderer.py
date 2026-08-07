from __future__ import annotations

import asyncio
import html
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.exceptions import AppError
from app.core.response_cache import ResponseHotCache
from app.services.seo import (
    SeoPageDocument,
    SeoPageLink,
    SeoPagePost,
    format_datetime,
    site_brand_name,
)

SEO_HEAD_START_MARKER = "<!-- parallellines-seo-head-start -->"
SEO_HEAD_END_MARKER = "<!-- parallellines-seo-head-end -->"
SEO_BODY_MARKER = "<!-- parallellines-seo-body -->"
SEO_SITE_STRUCTURED_DATA_ID = "seo-site-structured-data"
SEO_PAGE_STRUCTURED_DATA_ID = "seo-page-structured-data"
APP_SHELL_CACHE_TTL_SECONDS = 30
APP_SHELL_FETCH_TIMEOUT_SECONDS = 2.0
APP_SHELL_MAX_BYTES = 2 * 1024 * 1024

_APP_SHELL_CACHE = ResponseHotCache[str](
    ttl_seconds=APP_SHELL_CACHE_TTL_SECONDS,
    max_entries=4,
)


async def load_app_shell(shell_url: str) -> str:
    """Load and validate the compiled Web shell from trusted ``shell_url``.

    The URL comes only from runtime configuration, never request input. The
    returned UTF-8 HTML is capped by size and cached briefly in process; network
    and marker failures raise a typed 503 without exposing the internal URL.
    """

    cached = _APP_SHELL_CACHE.get(shell_url)
    if cached is not None:
        return cached
    try:
        shell = await asyncio.to_thread(_read_app_shell, shell_url)
    except (HTTPError, URLError, OSError, UnicodeError, ValueError) as exc:
        raise AppError(
            "seo_shell_unavailable",
            "Compiled Web shell is unavailable",
            status_code=503,
        ) from exc
    validate_app_shell(shell)
    _APP_SHELL_CACHE.set(shell_url, shell)
    return shell


def render_seo_document(
    shell: str,
    document: SeoPageDocument,
    *,
    baidu_site_verification: str | None = None,
) -> str:
    """Inject ``document`` metadata and semantic fallback into compiled ``shell``.

    The returned HTML preserves Vite-generated scripts and hashed assets. Marker
    cardinality is revalidated, all dynamic text/attributes are escaped, JSON-LD
    is script-safe, and optional Baidu verification content is emitted as an
    escaped meta tag. The pure transformation has no side effects.
    """

    validate_app_shell(shell)
    start_index = shell.index(SEO_HEAD_START_MARKER)
    end_index = shell.index(SEO_HEAD_END_MARKER) + len(SEO_HEAD_END_MARKER)
    rendered_head = render_seo_head(
        document,
        baidu_site_verification=baidu_site_verification,
    )
    with_head = f"{shell[:start_index]}{rendered_head}{shell[end_index:]}"
    return with_head.replace(SEO_BODY_MARKER, render_semantic_fallback(document), 1)


def validate_app_shell(shell: str) -> None:
    """Require each controlled SEO marker to occur exactly once in ``shell``.

    The function returns ``None`` on success and raises a typed 503 on missing,
    duplicate, or reversed markers. It performs no mutation or network access.
    """

    markers = (SEO_HEAD_START_MARKER, SEO_HEAD_END_MARKER, SEO_BODY_MARKER)
    if any(shell.count(marker) != 1 for marker in markers):
        raise AppError(
            "seo_shell_marker_mismatch",
            "Compiled Web shell SEO markers are invalid",
            status_code=503,
        )
    if shell.index(SEO_HEAD_START_MARKER) >= shell.index(SEO_HEAD_END_MARKER):
        raise AppError(
            "seo_shell_marker_mismatch",
            "Compiled Web shell SEO markers are invalid",
            status_code=503,
        )


def render_seo_head(
    document: SeoPageDocument,
    *,
    baidu_site_verification: str | None = None,
) -> str:
    """Return the controlled head block for typed SEO ``document`` metadata.

    The output contains one title, canonical, robots, OpenGraph/Twitter set, and
    stable JSON-LD slots when provided. Optional Baidu verification content is
    escaped into one meta tag. The function has no side effects.
    """

    meta = document.meta
    site_title = html.escape(site_brand_name(document.site.title), quote=True)
    lines = [
        SEO_HEAD_START_MARKER,
        f"    <title>{html.escape(meta.title)}</title>",
        f'    <meta name="description" content="{html.escape(meta.description, quote=True)}" />',
        f'    <meta name="robots" content="{html.escape(meta.robots, quote=True)}" />',
    ]
    if baidu_site_verification:
        lines.append(
            '    <meta name="baidu-site-verification" '
            f'content="{html.escape(baidu_site_verification, quote=True)}" />'
        )
    lines.extend(
        [
            f'    <link rel="canonical" href="{html.escape(meta.canonical_url, quote=True)}" />',
            f'    <meta property="og:type" content="{html.escape(meta.og_type, quote=True)}" />',
            f'    <meta property="og:title" content="{html.escape(meta.og_title, quote=True)}" />',
            '    <meta property="og:description" '
            f'content="{html.escape(meta.og_description, quote=True)}" />',
            f'    <meta property="og:url" content="{html.escape(meta.og_url, quote=True)}" />',
            f'    <meta property="og:site_name" content="{site_title}" />',
            '    <meta property="og:locale" content="zh_CN" />',
            '    <meta name="twitter:card" '
            f'content="{html.escape(meta.twitter_card, quote=True)}" />',
            f'    <meta name="twitter:title" content="{html.escape(meta.og_title, quote=True)}" />',
            '    <meta name="twitter:description" '
            f'content="{html.escape(meta.og_description, quote=True)}" />',
        ]
    )
    if document.site_structured_data is not None:
        lines.append(
            render_structured_data_script(
                SEO_SITE_STRUCTURED_DATA_ID,
                document.site_structured_data,
            )
        )
    if document.page_structured_data is not None:
        lines.append(
            render_structured_data_script(
                SEO_PAGE_STRUCTURED_DATA_ID,
                document.page_structured_data,
            )
        )
    lines.append(SEO_HEAD_END_MARKER)
    return "\n".join(lines)


def render_structured_data_script(slot_id: str, value: dict[str, object]) -> str:
    """Serialize JSON-LD ``value`` into the controlled ``slot_id`` script element.

    ``slot_id`` is an internal constant and the mapping may contain user-derived
    public text. The returned markup escapes HTML-sensitive JSON characters so a
    closing-script sequence cannot terminate the element; no side effects occur.
    """

    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    safe_json = encoded.replace("&", "\\u0026").replace("<", "\\u003c").replace(
        ">", "\\u003e"
    )
    return (
        f'    <script id="{html.escape(slot_id, quote=True)}" '
        f'type="application/ld+json">{safe_json}</script>'
    )


def render_semantic_fallback(document: SeoPageDocument) -> str:
    """Return accessible public fallback HTML matching ``document`` and JSON-LD.

    The output always has a unique H1 and crawlable site navigation. Only typed
    public links/posts supplied by the service are rendered; restricted/missing
    documents therefore contain no entity data. The function has no side effects.
    """

    sections = [
        '<main class="seo-fallback" '
        f'data-seo-page-kind="{html.escape(document.kind, quote=True)}">',
        '  <nav aria-label="站点导航">',
        f'    <a href="/">{html.escape(document.site.title)}</a>',
        '    <a href="/boards">全部版块</a>',
        "  </nav>",
        f"  <h1>{html.escape(document.heading)}</h1>",
        f"  <p>{html.escape(document.intro)}</p>",
    ]
    if document.links:
        sections.extend(render_link_section(document.links))
    if document.posts:
        sections.extend(render_post_section(document.posts))
    sections.append("</main>")
    return "\n".join(sections)


def render_link_section(links: tuple[SeoPageLink, ...]) -> list[str]:
    """Return a semantic list for the typed public ``links`` collection.

    Labels, paths, and optional descriptions are contextually escaped. The list
    of HTML lines is returned without mutating the input.
    """

    lines = ["  <section>", "    <h2>相关公开内容</h2>", "    <ul>"]
    for link in links:
        lines.append(
            f'      <li><a href="{html.escape(link.path, quote=True)}">'
            f"{html.escape(link.label)}</a>"
        )
        if link.description:
            lines.append(f"        <p>{html.escape(link.description)}</p>")
        lines.append("      </li>")
    lines.extend(["    </ul>", "  </section>"])
    return lines


def render_post_section(posts: tuple[SeoPagePost, ...]) -> list[str]:
    """Return semantic articles for the bounded visible ``posts`` collection.

    Author labels/URLs and timestamps are escaped while ``content_html`` is the
    forum service's stored sanitized Markdown rendering. Returned HTML mirrors
    the JSON-LD subset and the function has no side effects.
    """

    lines = ["  <section>", "    <h2>讨论内容</h2>"]
    for post in posts:
        article_label = "主题正文" if post.post_number == 1 else f"回复 {post.post_number - 1}"
        author = html.escape(post.author_name)
        if post.author_path is not None:
            author = (
                f'<a href="{html.escape(post.author_path, quote=True)}">{author}</a>'
            )
        lines.extend(
            [
                f'    <article id="post-{post.post_number}">',
                f"      <h3>{article_label}</h3>",
                "      <p>"
                f"{author} · "
                f'<time datetime="{html.escape(format_datetime(post.published_at), quote=True)}">'
                f"{html.escape(format_datetime(post.published_at))}</time>"
                "</p>",
                f'      <div class="seo-fallback__post">{post.content_html}</div>',
                "    </article>",
            ]
        )
    lines.extend(["  </section>"])
    return lines


def invalidate_app_shell_cache() -> None:
    """Clear the in-process compiled-shell cache and return ``None``.

    This explicit side effect is used by deterministic tests or future deploy
    hooks; it does not touch files, remote state, or application content.
    """

    _APP_SHELL_CACHE.clear()


def _read_app_shell(shell_url: str) -> str:
    """Synchronously fetch bounded UTF-8 shell bytes from trusted ``shell_url``.

    The helper runs inside ``asyncio.to_thread``. It returns decoded HTML and
    raises standard URL/size/decode errors; its only side effect is the HTTP GET.
    """

    request = Request(
        shell_url,
        headers={
            "Accept": "text/html",
            "User-Agent": "ParallelLinesSeoRenderer/1.0",
        },
    )
    with urlopen(request, timeout=APP_SHELL_FETCH_TIMEOUT_SECONDS) as response:
        status_code = getattr(response, "status", 200)
        if status_code != 200:
            raise OSError(f"Web shell returned HTTP {status_code}")
        payload = response.read(APP_SHELL_MAX_BYTES + 1)
    if len(payload) > APP_SHELL_MAX_BYTES:
        raise ValueError("Compiled Web shell exceeds the configured size limit")
    return payload.decode("utf-8")
