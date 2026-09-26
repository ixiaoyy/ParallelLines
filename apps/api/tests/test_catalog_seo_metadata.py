from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.seo as seo_module
from app.services.seo import SeoService, SeoSiteIdentity, site_description
from app.services.seo_renderer import (
    SEO_BODY_MARKER,
    SEO_HEAD_END_MARKER,
    SEO_HEAD_START_MARKER,
    SEO_SITE_STRUCTURED_DATA_ID,
    render_semantic_fallback,
    render_seo_document,
)


@pytest.fixture
def catalog_home(monkeypatch):
    """用目录读取替身构造首页，任何数据库调用或计数写入都会直接失败。"""

    class ReadOnlySession:
        def __getattr__(self, name):
            raise AssertionError(f"SEO must not access a database in this test: {name}")

    session = ReadOnlySession()
    settings = object()
    calls = []
    projects = [
        SimpleNamespace(url="https://example.com/game", name="站外游戏", description="公开简介"),
        SimpleNamespace(url="/play/generals-soldiers", name="将军战小兵", description=None),
    ]

    class ReadOnlyCatalog:
        def __init__(self, actual_session, actual_settings):
            assert actual_session is session
            assert actual_settings is settings

        async def public_catalog(self, request=None):
            calls.append(request)
            return SimpleNamespace(categories=[SimpleNamespace(projects=projects)])

        def __getattr__(self, name):
            raise AssertionError(f"SEO must only read the public catalog: {name}")

    monkeypatch.setattr(seo_module, "CatalogService", ReadOnlyCatalog)
    monkeypatch.setattr(seo_module, "get_settings", lambda: settings)

    def build(title):
        identity = SeoSiteIdentity(title, "旧论坛副标题", "/logo-lines-mark.png")
        service = SeoService(cast(AsyncSession, session))

        async def read_identity():
            return identity

        monkeypatch.setattr(service, "_site_identity", read_identity)
        return service, identity, calls, projects

    return build


@pytest.mark.parametrize(
    ("title", "brand"),
    [
        ("平行线", "平行线 ParallelLines"),
        ("云游馆 & 游戏", "云游馆 & 游戏 ParallelLines"),
        ("平行线 ParallelLines", "平行线 ParallelLines"),
    ],
)
def test_home_metadata_and_social_schema_share_confirmed_copy(catalog_home, title, brand):
    service, identity, calls, projects = catalog_home(title)
    expected_title = f"AI 游戏 · GPT / Claude Code / Kimi · 点开即玩 | {brand}"
    expected_description = (
        f"{brand} 收录 AI 网页游戏，探索 GPT、Claude Code、Kimi 等工具带来的游戏创意。"
        "涵盖策略、卡牌、解谜、角色扮演与休闲玩法，按分类和热度发现游戏，点开即玩。"
    )
    meta = asyncio.run(service.meta_for_path("/", "https://pingxingxian.space"))
    assert calls == []
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    assert calls == [None]
    assert document.meta == meta
    assert meta.title == expected_title
    assert meta.description == site_description(identity) == expected_description
    assert meta.og_title == expected_title
    assert meta.og_description == expected_description
    assert meta.canonical_url == meta.og_url == "https://pingxingxian.space/"
    assert meta.robots == "index,follow"
    assert document.heading == identity.title
    assert document.intro == ""
    assert [link.path for link in document.links] == [project.url for project in projects]
    assert document.page_structured_data is None

    shell = (
        "<html><head>"
        f"{SEO_HEAD_START_MARKER}<title>AI游戏收录 · 旧品牌</title>{SEO_HEAD_END_MARKER}"
        '</head><body><div id="app">'
        f"{SEO_BODY_MARKER}</div></body></html>"
    )
    rendered = render_seo_document(shell, document)
    assert f"<title>{html.escape(expected_title)}</title>" in rendered
    for attribute, name in (
        ("name", "description"),
        ("property", "og:description"),
        ("name", "twitter:description"),
    ):
        assert (
            f'{attribute}="{name}" content="{html.escape(expected_description, quote=True)}"'
            in rendered
        )
    assert f'name="twitter:title" content="{html.escape(expected_title, quote=True)}"' in rendered
    assert f'property="og:site_name" content="{html.escape(brand, quote=True)}"' in rendered
    assert "AI游戏收录 · 旧品牌" not in rendered
    assert "旧论坛副标题" not in rendered
    assert 'name="keywords"' not in rendered

    match = re.search(
        rf'<script id="{SEO_SITE_STRUCTURED_DATA_ID}" type="application/ld\+json">(.*?)</script>',
        rendered,
    )
    assert match is not None
    website, organization = json.loads(match.group(1))["@graph"]
    assert website["@type"] == "WebSite"
    assert website["name"] == organization["name"] == brand
    assert website["description"] == expected_description
    assert website["alternateName"] == organization["alternateName"]
    assert "ParallelLines" in website["alternateName"]
    assert organization["logo"]["url"] == "https://pingxingxian.space/logo-lines-mark.png"


def test_empty_home_intro_does_not_render_an_extra_paragraph(catalog_home):
    service, _, _, _ = catalog_home("平行线")
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    rendered = render_semantic_fallback(replace(document, links=()))
    assert "<h1>平行线</h1>" in rendered
    assert "<p>" not in rendered
    assert "收录 AI 网页游戏" not in rendered


def test_nonempty_intro_keeps_existing_escaped_rendering(catalog_home):
    service, _, _, _ = catalog_home("平行线")
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    rendered = render_semantic_fallback(
        replace(document, links=(), intro='公开 <简介> & "说明"')
    )
    assert "<p>公开 &lt;简介&gt; &amp; &quot;说明&quot;</p>" in rendered
    assert "<简介>" not in rendered
