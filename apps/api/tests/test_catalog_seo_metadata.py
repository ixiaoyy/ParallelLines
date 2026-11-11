from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.seo as seo_module
from app.core.exceptions import NotFoundError
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

        async def public_project_links(self):
            calls.append(None)
            return projects

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
    expected_title = f"{brand}（pingxingxian）· 发现游戏、工具与创意"
    expected_description = (
        f"{brand}（pingxingxian）是发现游戏、实用工具与创意内容的空间。"
        "浏览游戏目录，探索办公与创作工具；兴趣圈子暂未开放。"
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
    assert document.intro == expected_description
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
    assert "pingxingxian" in website["alternateName"]
    assert organization["logo"]["url"] == "https://pingxingxian.space/logo-lines-mark.png"


def test_home_intro_renders_visible_site_brand_and_current_scope(catalog_home):
    service, _, _, _ = catalog_home("平行线")
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    rendered = render_semantic_fallback(replace(document, links=()))
    assert "<h1>平行线</h1>" in rendered
    assert f"<p>{html.escape(document.intro, quote=True)}</p>" in rendered
    assert "平行线 ParallelLines（pingxingxian）" in rendered
    assert "办公与创作工具" in rendered
    assert "兴趣圈子暂未开放" in rendered
    assert 'href="/forum"' not in rendered


def test_empty_intro_still_omits_extra_paragraph(catalog_home):
    service, _, _, _ = catalog_home("平行线")
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    rendered = render_semantic_fallback(replace(document, links=(), intro=""))
    assert "<p>" not in rendered


def test_nonempty_intro_keeps_existing_escaped_rendering(catalog_home):
    service, _, _, _ = catalog_home("平行线")
    document = asyncio.run(service.home_page("https://pingxingxian.space"))
    rendered = render_semantic_fallback(
        replace(document, links=(), intro='公开 <简介> & "说明"')
    )
    assert "<p>公开 &lt;简介&gt; &amp; &quot;说明&quot;</p>" in rendered
    assert "<简介>" not in rendered


@pytest.mark.parametrize("path", ["/games", "/games/?utm_source=catalog", "/?utm_source=legacy"])
def test_games_metadata_uses_canonical_directory_without_reading_catalog(catalog_home, path):
    service, _, calls, _ = catalog_home("平行线")
    meta = asyncio.run(service.meta_for_path(path, "https://pingxingxian.space"))
    assert meta.canonical_url == meta.og_url == "https://pingxingxian.space/"
    assert calls == []


def test_catalog_sitemap_includes_only_root_and_registered_games(catalog_home):
    service, _, calls, _ = catalog_home("平行线")
    urls = asyncio.run(service.sitemap_urls("https://pingxingxian.space"))
    assert [item.loc for item in urls] == [
        "https://pingxingxian.space/",
        "https://pingxingxian.space/play/generals-soldiers",
        "https://pingxingxian.space/play/snake-escape",
        "https://pingxingxian.space/play/flappy-dunk",
    ]
    assert all(item.lastmod is None for item in urls)
    assert calls == []


@pytest.mark.parametrize(
    ("path", "name", "description"),
    [
        (
            "/play/generals-soldiers",
            "将军战小兵",
            "在平行线与电脑进行将军战小兵对弈。",
        ),
        (
            "/play/snake-escape",
            "蛇蛇出洞",
            "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
        ),
        (
            "/play/flappy-dunk",
            "飞翼灌篮",
            "点按让带翅膀的篮球跳跃，从上方穿过篮圈，挑战连续进球和最高分。",
        ),
    ],
)
def test_public_game_initial_html_matches_its_own_metadata(catalog_home, path, name, description):
    """真实渲染三游戏首屏，禁止查询目录、评分或写入游戏统计。"""

    service, identity, calls, _ = catalog_home("云游馆 & 游戏")
    origin = "https://pingxingxian.space"
    document = asyncio.run(service.game_page(f"{path}/?utm_source=bookmark#game", origin))
    meta = asyncio.run(service.meta_for_path(f"{path}?utm_source=bookmark", origin))
    assert document.meta == meta
    assert meta.title == f"{name} · {identity.title}"
    assert meta.description == description
    assert meta.canonical_url == meta.og_url == f"{origin}{path}"
    assert meta.robots == "index,follow"
    assert document.kind == "game"
    assert document.heading == name
    assert document.intro == description
    assert document.links == document.posts == ()
    assert document.page_structured_data is None
    assert calls == []

    shell = (
        "<html><head>"
        f"{SEO_HEAD_START_MARKER}<title>目录标题</title>{SEO_HEAD_END_MARKER}"
        '<link rel="stylesheet" href="/assets/app.hash.css"></head>'
        f'<body><div id="app">{SEO_BODY_MARKER}</div>'
        '<script src="/assets/app.hash.js"></script></body></html>'
    )
    rendered = render_seo_document(shell, document)
    assert rendered.count('<link rel="canonical"') == 1
    assert f'<link rel="canonical" href="{origin}{path}"' in rendered
    assert f"<title>{html.escape(meta.title)}</title>" in rendered
    assert f"<h1>{name}</h1>" in rendered
    assert f"<p>{description}</p>" in rendered
    assert '<a href="/">云游馆 &amp; 游戏</a>' in rendered
    assert 'href="/forum"' not in rendered
    assert "/assets/app.hash.css" in rendered
    assert "/assets/app.hash.js" in rendered
    assert rendered.count(f'id="{SEO_SITE_STRUCTURED_DATA_ID}"') == 1
    website = document.site_structured_data["@graph"][0]
    assert website["description"] == site_description(identity)
    assert website["url"] == f"{origin}/"


def test_unregistered_game_does_not_read_brand_or_catalog(catalog_home, monkeypatch):
    service, _, calls, _ = catalog_home("平行线")

    async def fail_brand_read():
        raise AssertionError("Unknown game must not access branding")

    monkeypatch.setattr(service, "_site_identity", fail_brand_read)
    with pytest.raises(NotFoundError, match="SEO game page not found"):
        asyncio.run(service.game_page("/play/not-registered", "https://pingxingxian.space"))
    assert calls == []


@pytest.mark.parametrize("slug", ["generals-soldiers", "snake-escape", "flappy-dunk"])
def test_public_game_nginx_handoff_preserves_redirect_and_5xx_only_fallback(slug):
    """检查三游戏的静态接线合同，不把配置文本检查当成 Nginx 运行验收。"""

    config = (Path(__file__).parents[3] / "deploy/nginx/default.conf").read_text(encoding="utf-8")
    page_block = re.search(rf"location = /play/{slug} \{{(.*?)\n    \}}", config, re.S)
    slash_block = re.search(rf"location = /play/{slug}/ \{{(.*?)\n    \}}", config, re.S)
    assert page_block is not None
    assert slash_block is not None
    assert "proxy_pass http://$api_upstream;" in page_block.group(1)
    assert "proxy_intercept_errors on;" in page_block.group(1)
    assert "error_page 500 502 503 504 = @web_page_fallback;" in page_block.group(1)
    assert "error_page 301" not in page_block.group(1)
    assert "error_page 404" not in page_block.group(1)
    assert f"return 301 /play/{slug};" in slash_block.group(1)


def test_tools_page_exposes_only_current_empty_state(catalog_home):
    service, _, calls, _ = catalog_home("平行线")
    origin = "https://pingxingxian.space"
    expected_copy = "暂无可用工具。工具开放后会显示在这里。"
    meta = asyncio.run(service.meta_for_path("/tools?source=navigation", origin))
    document = asyncio.run(service.tools_page(origin))
    assert calls == []
    assert document.status_code == 200
    assert document.heading == "工具"
    assert document.intro == expected_copy
    assert document.meta == meta
    assert meta.title == "工具 · 平行线 ParallelLines"
    assert meta.description == expected_copy
    assert meta.canonical_url == meta.og_url == f"{origin}/tools"
    assert document.links == ()
    assert document.posts == ()
    assert document.page_structured_data is None

    rendered = render_semantic_fallback(document)
    assert '<a href="/">平行线</a>' in rendered
    assert f"<p>{expected_copy}</p>" in rendered
    assert "相关公开内容" not in rendered
    assert 'href="/forum"' not in rendered
    assert "圈子" not in rendered
