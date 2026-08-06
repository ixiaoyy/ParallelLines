from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.seo import base_url
from app.core.config import Settings
from app.core.exceptions import AppError
from app.schemas.seo import SeoMetaResponse, SitemapUrl
from app.services.seo import SeoPageDocument, SeoPageLink, SeoService, SeoSiteIdentity
from app.services.seo_renderer import (
    SEO_BODY_MARKER,
    SEO_HEAD_END_MARKER,
    SEO_HEAD_START_MARKER,
    SEO_PAGE_STRUCTURED_DATA_ID,
    render_seo_document,
    validate_app_shell,
)


def app_shell() -> str:
    return (
        "<!doctype html><html><head>"
        f"{SEO_HEAD_START_MARKER}<title>default</title>{SEO_HEAD_END_MARKER}"
        "<link rel=\"stylesheet\" href=\"/assets/app.hash.css\"></head>"
        f"<body><div id=\"app\">{SEO_BODY_MARKER}</div>"
        "<script src=\"/assets/app.hash.js\"></script></body></html>"
    )


def page_document(*, robots: str = "index,follow") -> SeoPageDocument:
    meta = SeoMetaResponse(
        title='标题 </title><script>alert("x")</script>',
        description='描述 "><script>alert(1)</script>',
        canonical_url="https://pingxingxian.space/topics/1/topic",
        robots=robots,
        og_type="article",
        og_title="公开主题",
        og_description="公开描述",
        og_url="https://pingxingxian.space/topics/1/topic",
    )
    return SeoPageDocument(
        kind="topic",
        status_code=200,
        site=SeoSiteIdentity(
            title="平行线",
            tagline="让答案可追溯",
            logo_url="/logo-lines-mark.png",
        ),
        meta=meta,
        heading="公开 <主题>",
        intro="公开简介",
        links=(
            SeoPageLink(
                path='/b/public\" onclick=\"alert(1)',
                label="公开 & 版块",
                description="可见内容",
            ),
        ),
        page_structured_data={
            "@context": "https://schema.org",
            "@type": "DiscussionForumPosting",
            "headline": "中文主题",
            "text": "</script><script>alert('json')</script> & 正文",
        },
    )


def test_renderer_preserves_vite_assets_and_escapes_dynamic_html() -> None:
    rendered = render_seo_document(app_shell(), page_document())

    assert "/assets/app.hash.css" in rendered
    assert "/assets/app.hash.js" in rendered
    assert "<title>标题 &lt;/title&gt;&lt;script&gt;" in rendered
    assert "<h1>公开 &lt;主题&gt;</h1>" in rendered
    assert 'onclick="alert(1)' not in rendered
    assert "公开 &amp; 版块" in rendered
    assert rendered.count('rel="canonical"') == 1


def test_renderer_keeps_json_ld_parseable_and_script_safe() -> None:
    rendered = render_seo_document(app_shell(), page_document())
    pattern = re.compile(
        rf'<script id="{SEO_PAGE_STRUCTURED_DATA_ID}" type="application/ld\+json">(.*?)</script>'
    )
    match = pattern.search(rendered)

    assert match is not None
    payload = match.group(1)
    assert "</script>" not in payload.lower()
    assert "\\u003c/script\\u003e" in payload.lower()
    parsed = json.loads(payload)
    assert parsed["headline"] == "中文主题"
    assert parsed["text"].startswith("</script>")


@pytest.mark.parametrize(
    "broken_shell",
    [
        "<html><head></head><body></body></html>",
        app_shell().replace(SEO_BODY_MARKER, SEO_BODY_MARKER * 2),
        app_shell().replace(SEO_HEAD_START_MARKER, "").replace(
            SEO_HEAD_END_MARKER,
            f"{SEO_HEAD_END_MARKER}{SEO_HEAD_START_MARKER}",
        ),
    ],
)
def test_shell_marker_mismatch_is_a_typed_503(broken_shell: str) -> None:
    with pytest.raises(AppError) as error:
        validate_app_shell(broken_shell)

    assert error.value.code == "seo_shell_marker_mismatch"
    assert error.value.status_code == 503


def test_sitemap_serialization_omits_ignored_priority_and_change_frequency() -> None:
    service = SeoService(cast(AsyncSession, object()))
    xml = service.build_sitemap_xml(
        [
            SitemapUrl(
                loc="https://pingxingxian.space/topics/1/topic?a=1&b=2",
                lastmod=datetime(2026, 8, 6, 12, 30, tzinfo=UTC),
            )
        ]
    )

    assert "<changefreq>" not in xml
    assert "<priority>" not in xml
    assert "2026-08-06T12:30:00Z" in xml
    assert "?a=1&amp;b=2" in xml


def test_configured_canonical_origin_ignores_request_host_and_forwarded_headers() -> None:
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/sitemap.xml",
            "raw_path": b"/sitemap.xml",
            "query_string": b"",
            "server": ("attacker.invalid", 80),
            "client": ("127.0.0.1", 12345),
            "headers": [
                (b"host", b"attacker.invalid"),
                (b"x-forwarded-proto", b"http"),
            ],
        }
    )
    settings = Settings(public_site_url="https://pingxingxian.space/")

    assert base_url(request, settings) == "https://pingxingxian.space"


def test_canonical_config_rejects_paths_and_non_http_schemes() -> None:
    with pytest.raises(ValidationError):
        Settings(public_site_url="https://pingxingxian.space/forum")
    with pytest.raises(ValidationError):
        Settings(web_app_shell_url="file:///tmp/index.html")


@pytest.mark.asyncio
async def test_content_activity_queries_compile_without_database_access() -> None:
    """Compile content-activity SQL through the production MySQL dialect only."""

    class CompilingSession:
        """Compile read statements and return empty rows without opening a connection."""

        async def execute(self, statement: object) -> list[object]:
            """Compile ``statement`` for MySQL and return an empty iterable result."""

            statement.compile(dialect=mysql.dialect())  # type: ignore[attr-defined]
            return []

    service = SeoService(cast(AsyncSession, CompilingSession()))

    assert await service._public_user_activity() == {}  # noqa: SLF001
    assert await service._public_topic_content_activity() == {}  # noqa: SLF001
    assert await service._post_revision_activity(("1", "2")) == {}  # noqa: SLF001
