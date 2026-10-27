from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.seo as seo_api
import app.services.seo as seo_module
from app.core.exceptions import NotFoundError
from app.db.session import get_session
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


@pytest.mark.parametrize("path", ["/games", "/games/?utm_source=catalog", "/?utm_source=legacy"])
def test_games_metadata_uses_canonical_directory_without_reading_catalog(catalog_home, path):
    service, _, calls, _ = catalog_home("平行线")
    meta = asyncio.run(service.meta_for_path(path, "https://pingxingxian.space"))
    assert meta.canonical_url == meta.og_url == "https://pingxingxian.space/"
    assert calls == []


def test_catalog_sitemap_uses_canonical_root_entry(catalog_home):
    service, _, calls, _ = catalog_home("平行线")
    urls = asyncio.run(service.sitemap_urls("https://pingxingxian.space"))
    assert [item.loc for item in urls] == [
        "https://pingxingxian.space/",
        "https://pingxingxian.space/tools",
        "https://pingxingxian.space/tools/excel-formulas",
        "https://pingxingxian.space/tools/bead-pattern",
        "https://pingxingxian.space/play/generals-soldiers",
        "https://pingxingxian.space/play/snake-escape",
        "https://pingxingxian.space/play/flappy-dunk",
    ]
    assert all(item.lastmod is None for item in urls)
    assert calls == []


def test_tools_page_exposes_registered_tools_without_forum_content(catalog_home):
    service, _, calls, _ = catalog_home("平行线")
    origin = "https://pingxingxian.space"
    expected_copy = (
        "Excel 公式速查与拼豆图纸生成器，支持公式学习、图片转换、色号用量统计与图纸导出。"
    )
    meta = asyncio.run(service.meta_for_path("/tools?source=navigation", origin))
    document = asyncio.run(service.tools_page(origin))
    assert calls == []
    assert document.status_code == 200
    assert document.heading == "工具"
    assert document.intro == expected_copy
    assert document.meta == meta
    assert meta.title == "工具 · 平行线"
    assert meta.description == expected_copy
    assert meta.canonical_url == meta.og_url == f"{origin}/tools"
    assert [(link.path, link.label, link.description) for link in document.links] == [
        ("/tools/excel-formulas", "Excel 公式速查", "文职常用公式，按步骤照着做。"),
        ("/tools/bead-pattern", "拼豆图纸生成器", "将图片转换为拼豆图纸，查看色号和用量。"),
    ]
    assert document.posts == ()
    assert document.page_structured_data is None
    assert (
        document.site_structured_data["@graph"][0]["description"] == site_description(document.site)
    )

    rendered = render_semantic_fallback(document)
    assert '<a href="/">平行线</a>' in rendered
    assert f"<p>{expected_copy}</p>" in rendered
    assert '<a href="/tools/excel-formulas">Excel 公式速查</a>' in rendered
    assert '<a href="/tools/bead-pattern">拼豆图纸生成器</a>' in rendered
    assert "暂无可用工具" not in rendered
    assert 'href="/play/' not in rendered
    assert 'href="/forum"' not in rendered
    assert "圈子" not in rendered


@pytest.mark.parametrize(
    ("path", "heading", "description", "return_path", "return_label"),
    [
        (
            "/tools/excel-formulas", "Excel 公式速查", "文职常用公式，按步骤照着做。",
            "/tools", "返回工具列表",
        ),
        (
            "/tools/bead-pattern", "拼豆图纸生成器", "将图片转换为拼豆图纸，查看色号和用量。",
            "/tools", "返回工具列表",
        ),
        (
            "/play/generals-soldiers", "将军战小兵", "在平行线与电脑进行将军战小兵对弈。",
            "/", "返回游戏目录",
        ),
        (
            "/play/snake-escape", "蛇蛇出洞",
            "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
            "/", "返回游戏目录",
        ),
        (
            "/play/flappy-dunk", "飞翼灌篮",
            "点按让带翅膀的篮球跳跃，从上方穿过篮圈，挑战连续进球和最高分。",
            "/", "返回游戏目录",
        ),
    ],
)
def test_interactive_details_match_existing_copy_and_keep_canonical(
    catalog_home, path, heading, description, return_path, return_label
):
    service, _, calls, _ = catalog_home("平行线")
    origin = "https://pingxingxian.space"
    requested_path = f"{path}/?lesson=person-total&utm_source=test#preview"
    meta = asyncio.run(service.meta_for_path(requested_path, origin))
    document = asyncio.run(service.interactive_page(requested_path, origin))
    assert calls == []
    assert document.meta == meta
    assert document.status_code == 200
    assert document.kind == ("tools" if path.startswith("/tools/") else "game")
    assert document.heading == heading
    assert document.intro == meta.description == meta.og_description == description
    assert meta.title == meta.og_title == f"{heading} · 平行线"
    assert meta.canonical_url == meta.og_url == f"{origin}{path}"
    assert meta.robots == "index,follow"
    assert [(link.path, link.label) for link in document.links] == [(return_path, return_label)]
    assert document.posts == ()
    assert document.page_structured_data is None
    assert (
        document.site_structured_data["@graph"][0]["description"] == site_description(document.site)
    )
    rendered = render_semantic_fallback(document)
    assert f"<h1>{heading}</h1>" in rendered
    assert f'<a href="{return_path}">{return_label}</a>' in rendered
    assert 'href="/forum"' not in rendered


@pytest.mark.parametrize("path", ["/tools/unregistered", "/play/unregistered"])
def test_unregistered_interactive_details_are_not_reused(catalog_home, path):
    service, _, calls, _ = catalog_home("平行线")
    with pytest.raises(NotFoundError):
        asyncio.run(service.interactive_page(path, "https://pingxingxian.space"))
    with pytest.raises(NotFoundError):
        asyncio.run(service.meta_for_path(path, "https://pingxingxian.space"))
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/tools/excel-formulas", "/tools/excel-formulas/",
        "/tools/bead-pattern", "/tools/bead-pattern/",
        "/play/generals-soldiers", "/play/snake-escape", "/play/flappy-dunk",
    ],
)
async def test_registered_detail_http_routes_render_without_redirect(
    catalog_home, monkeypatch, path
):
    service, _, calls, _ = catalog_home("平行线")
    app = FastAPI()
    app.include_router(seo_api.public_seo_router)
    app.dependency_overrides[get_session] = lambda: service.session
    monkeypatch.setattr(seo_api, "SeoService", lambda session: service)
    monkeypatch.setattr(seo_api, "get_settings", lambda: SimpleNamespace(
        public_site_url="https://pingxingxian.space",
        web_app_shell_url="http://web/index.html",
        baidu_site_verification=None,
    ))

    async def load_shell(_url):
        return (
            f"<html><head>{SEO_HEAD_START_MARKER}<title>old</title>{SEO_HEAD_END_MARKER}"
            '<link rel="stylesheet" href="/assets/app.hash.css"></head><body><div id="app">'
            f'{SEO_BODY_MARKER}</div><script src="/assets/app.hash.js"></script></body></html>'
        )

    monkeypatch.setattr(seo_api, "load_app_shell", load_shell)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://forged.example"
    ) as client:
        response = await client.get(f"{path}?lesson=person-total&utm_source=test")

    canonical_path = path.rstrip("/")
    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.headers["cache-control"] == "no-cache"
    assert response.text.count('rel="canonical"') == 1
    assert f'href="https://pingxingxian.space{canonical_path}"' in response.text
    assert "/assets/app.hash.css" in response.text
    assert "/assets/app.hash.js" in response.text
    assert "暂无可用工具" not in response.text
    assert calls == []
    route = next(route for route in seo_api.public_seo_router.routes if route.path == path)
    assert route.include_in_schema is False
