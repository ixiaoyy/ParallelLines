from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

import app.api.seo as seo_api
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.session import get_session
from app.schemas.seo import SeoMetaResponse
from app.services.seo import LegacyTopicRedirect, SeoPageDocument, SeoService, SeoSiteIdentity
from app.services.seo_renderer import SEO_BODY_MARKER, SEO_HEAD_END_MARKER, SEO_HEAD_START_MARKER

MAIN = "https://pingxingxian.space"
FORUM = "https://forum.pingxingxian.space"


def request_for(host: str, *, forwarded: str = "") -> Request:
    """构造无网络的请求，单独验证固定来源匹配和恶意转发头。"""

    return Request({
        "type": "http", "scheme": "http", "method": "GET", "path": "/",
        "query_string": b"", "server": (host, 80),
        "headers": [(b"host", host.encode()), (b"x-forwarded-host", forwarded.encode())],
    })


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(
        _env_file=None, public_site_url=MAIN, public_forum_url=FORUM,
        web_app_shell_url="http://web/index.html",
        forum_web_app_shell_url="http://forum-web/index.html",
    )
    monkeypatch.setattr(seo_api, "get_settings", lambda: settings)
    seo_api.invalidate_sitemap_response_cache()
    yield settings
    seo_api.invalidate_sitemap_response_cache()


def test_forum_config_is_optional_and_preserves_old_origins():
    settings = Settings(_env_file=None, public_site_url=MAIN, public_forum_url=None)
    request = request_for("attacker.invalid", forwarded="forum.pingxingxian.space")
    assert seo_api.base_url(request, settings) == MAIN
    assert seo_api.forum_base_url(request, settings) == MAIN
    assert not seo_api.is_forum_request(request, settings)


@pytest.mark.parametrize("value", [
    "file:///index.html", "https://forum.test/path", "https://forum.test?q=x",
    "https://forum.test/#x", "https://user:secret@forum.test", "//forum.test", "",
])
def test_forum_config_rejects_non_origins(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, public_forum_url=value)


def test_forum_shell_config_reuses_existing_http_validation():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, forum_web_app_shell_url="file:///index.html")
    settings = Settings(_env_file=None, public_forum_url=f"{FORUM}/")
    assert settings.public_forum_url == FORUM


def test_request_host_only_selects_configured_forum_origin(configured):
    assert seo_api.is_forum_request(request_for("forum.pingxingxian.space"), configured)
    assert seo_api.is_forum_request(request_for("FORUM.PINGXINGXIAN.SPACE"), configured)
    assert not seo_api.is_forum_request(request_for("forum.pingxingxian.space:9999"), configured)
    attack = request_for("attacker.invalid", forwarded="forum.pingxingxian.space")
    assert not seo_api.is_forum_request(attack, configured)
    assert seo_api.forum_base_url(attack, configured) == FORUM
    assert seo_api.base_url(attack, configured) == MAIN


@pytest.fixture
def public_service(monkeypatch):
    """仅提供已分类公开内容；任何真实数据库访问都会立即失败。"""

    class NoDatabase:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected database access: {name}")

    service = SeoService(cast(AsyncSession, NoDatabase()))
    identity = SeoSiteIdentity("平行线", "让答案可追溯", "/logo-lines-mark.png")
    monkeypatch.setattr(service, "_site_identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(service, "_public_boards", AsyncMock(return_value=[
        SimpleNamespace(slug="public", name="公开版块", description="简介"),
    ]))
    monkeypatch.setattr(service, "_public_topics", AsyncMock(return_value=[
        SimpleNamespace(id="1", slug="public-topic", title="公开主题", reply_count=0, view_count=1),
    ]))
    monkeypatch.setattr(service, "_public_users", AsyncMock(return_value=[SimpleNamespace(id="2")]))
    return service


@pytest.mark.asyncio
async def test_forum_sitemap_is_separate_bounded_and_does_not_invent_timestamps(public_service):
    service = public_service
    urls = await service.forum_sitemap_urls(FORUM)
    assert [item.loc for item in urls] == [
        f"{FORUM}/", f"{FORUM}/boards", f"{FORUM}/b/public",
        f"{FORUM}/topics/1/public-topic", f"{FORUM}/members/2",
    ]
    assert all(item.lastmod is None for item in urls)
    service._public_boards.assert_awaited_once_with(1000)
    service._public_topics.assert_awaited_once_with(1000)
    service._public_users.assert_awaited_once_with(1000)
    assert all("/play/" not in item.loc for item in urls)
    assert all("/topics/" not in item.loc for item in await service.sitemap_urls(MAIN))


@pytest.mark.asyncio
async def test_sitemap_reuses_three_public_filter_queries_without_a_connection():
    statements = []

    class CompileOnly:
        async def scalars(self, statement):
            statements.append(str(statement.compile(dialect=mysql.dialect(), compile_kwargs={
                "literal_binds": True,
            })))
            return []

    service = SeoService(cast(AsyncSession, CompileOnly()))
    assert len(await service.forum_sitemap_urls(FORUM)) == 2
    assert len(statements) == 3
    assert "boards.visibility = 'public'" in statements[0]
    assert "topics.visibility = 'public'" in statements[1]
    assert "topics.deleted_at IS NULL" in statements[1]
    assert "topics.merged_into_topic_id IS NULL" in statements[1]
    assert "topics.status != 'hidden'" in statements[1]
    assert "users.status = 'active'" in statements[2]
    assert "users.profile_visibility = 'public'" in statements[2]
    assert all("LIMIT 1000" in statement for statement in statements)


@pytest.fixture
def isolated_app(configured, public_service, monkeypatch):
    """ASGI 路由使用真实序列化/渲染及内容替身，不运行数据库和 HTTP 外壳读取。"""

    service = public_service
    monkeypatch.setattr(seo_api, "SeoService", lambda session: service)
    main_meta = SeoMetaResponse(
        title="游戏目录", description="目录介绍", canonical_url=f"{MAIN}/", og_type="website",
        og_title="游戏目录", og_description="目录介绍", og_url=f"{MAIN}/",
    )
    game_doc = SeoPageDocument(
        kind="home", status_code=200,
        site=SeoSiteIdentity("平行线", "简介", "/logo-lines-mark.png"),
        meta=main_meta, heading="游戏目录", intro="目录介绍",
    )
    monkeypatch.setattr(service, "home_page", AsyncMock(return_value=game_doc))
    monkeypatch.setattr(service, "legacy_topic_redirect", AsyncMock(return_value=
        LegacyTopicRedirect(status_code=301, location=f"{FORUM}/topics/1/public-topic")))

    async def shell(url):
        return (
            f"<html><head>{SEO_HEAD_START_MARKER}{SEO_HEAD_END_MARKER}</head><body>"
            f"<div data-shell='{url}'>{SEO_BODY_MARKER}</div>"
            "<script src='/assets/app.hash.js'></script></body></html>"
        )

    monkeypatch.setattr(seo_api, "load_app_shell", shell)
    app = FastAPI()
    app.include_router(seo_api.public_seo_router)
    app.include_router(seo_api.api_seo_router, prefix="/api/v1")

    async def no_database_session():
        yield object()

    app.dependency_overrides[get_session] = no_database_session
    return app


@pytest.mark.asyncio
async def test_both_roots_render_their_own_content_shell_and_canonical(isolated_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        main = await client.get(f"{MAIN}/?source=main")
        games = await client.get(f"{MAIN}/games")
        forum = await client.get(f"{FORUM}/?source=forum")
    assert main.status_code == games.status_code == forum.status_code == 200
    assert '<h1>游戏目录</h1>' in main.text
    assert 'data-shell=\'http://web/index.html\'' in main.text
    assert f'rel="canonical" href="{MAIN}/"' in main.text
    assert '<h1>游戏目录</h1>' not in forum.text
    assert 'data-shell=\'http://forum-web/index.html\'' in forum.text
    assert f'rel="canonical" href="{FORUM}/"' in forum.text
    assert "<title>平行线 ParallelLines · 圈子</title>" in forum.text
    assert 'property="og:title" content="平行线 ParallelLines · 圈子"' in forum.text
    assert '<a href="/">平行线</a>' in forum.text
    assert '/assets/app.hash.js' in forum.text


@pytest.mark.asyncio
async def test_old_forum_entry_and_topic_aliases_redirect_to_fixed_forum(isolated_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        for host in [MAIN, FORUM]:
            response = await client.get(
                f"{host}/forum?tag=one&tag=two&empty=", follow_redirects=False,
            )
            assert response.status_code == 301
            assert response.headers["location"] == f"{FORUM}/?tag=one&tag=two&empty="
        for path in ["/t/old-title/1", "/p/1"]:
            response = await client.get(f"{MAIN}{path}", follow_redirects=False)
            assert response.status_code == 301
            assert response.headers["location"] == f"{FORUM}/topics/1/public-topic"


@pytest.mark.asyncio
async def test_sitemap_cache_and_robots_remain_separate_by_configured_site(isolated_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        main = await client.get(f"{MAIN}/sitemap.xml")
        forum = await client.get(f"{FORUM}/sitemap.xml")
        cached_forum = await client.get(f"{FORUM}/sitemap.xml")
        assert main.headers["x-parallellines-cache"] == "miss"
        assert forum.headers["x-parallellines-cache"] == "miss"
        assert cached_forum.headers["x-parallellines-cache"] == "hit"
        assert "/play/" in main.text and "/topics/" not in main.text
        assert "/topics/1/public-topic" in forum.text and "/play/" not in forum.text
        for origin in [MAIN, FORUM]:
            robots = await client.get(f"{origin}/robots.txt")
            assert f"Sitemap: {origin}/sitemap.xml" in robots.text


@pytest.mark.asyncio
async def test_metadata_uses_forum_root_and_fixed_forum_content_origins(isolated_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        forum_root = await client.get(f"{FORUM}/api/v1/seo/meta?path=/")
        old_entry = await client.get(f"{MAIN}/api/v1/seo/meta?path=/forum")
        boards = await client.get(f"{MAIN}/api/v1/seo/meta?path=/boards")
        main = await client.get(f"{MAIN}/api/v1/seo/meta?path=/")
    assert forum_root.json()["data"]["canonical_url"] == f"{FORUM}/"
    assert old_entry.json()["data"]["canonical_url"] == f"{FORUM}/"
    assert forum_root.json()["data"]["title"] == "平行线 ParallelLines · 圈子"
    assert old_entry.json()["data"]["title"] == "平行线 ParallelLines · 圈子"
    assert boards.json()["data"]["canonical_url"] == f"{FORUM}/boards"
    assert main.json()["data"]["canonical_url"] == f"{MAIN}/"


@pytest.mark.asyncio
async def test_forum_shell_failure_does_not_load_the_main_shell(
    configured, public_service, monkeypatch,
):
    document = await public_service.forum_page(FORUM, canonical_path="/")
    configured.forum_web_app_shell_url = None
    load = AsyncMock()
    monkeypatch.setattr(seo_api, "load_app_shell", load)
    with pytest.raises(AppError, match="Compiled Web shell URL is not configured") as failure:
        await seo_api.html_page_response(document)
    assert failure.value.status_code == 503
    load.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "method", "arguments"), [
    ("/boards", "boards_page", (FORUM,)),
    ("/b/public", "board_page", ("public", FORUM)),
    ("/topics/1/public-topic", "topic_page", ("1", "public-topic", FORUM)),
    ("/topics/1", "topic_page", ("1", None, FORUM)),
    ("/members/2", "profile_page", ("2", FORUM)),
])
async def test_forum_public_routes_use_forum_origin_on_both_hosts(
    isolated_app, public_service, monkeypatch, path, method, arguments,
):
    document = await public_service.forum_page(FORUM, canonical_path="/")
    read = AsyncMock(return_value=document)
    monkeypatch.setattr(public_service, method, read)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        for origin in [MAIN, FORUM]:
            response = await client.get(f"{origin}{path}")
            assert response.status_code == 200
            assert 'data-shell=\'http://forum-web/index.html\'' in response.text
    assert read.await_args_list[0].args == arguments
    assert read.await_args_list[1].args == arguments


@pytest.mark.asyncio
@pytest.mark.parametrize(("board", "status"), [(None, 404), (
    SimpleNamespace(visibility="private", name="不能公开的版块"), 200,
)])
async def test_forum_missing_and_private_documents_keep_status_and_noindex(
    isolated_app, public_service, monkeypatch, board, status,
):
    monkeypatch.setattr(public_service, "_board_by_slug", AsyncMock(return_value=board))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated_app)) as client:
        response = await client.get(f"{FORUM}/b/unknown")
    assert response.status_code == status
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert f'rel="canonical" href="{FORUM}/b/unknown"' in response.text
    assert 'data-shell=\'http://forum-web/index.html\'' in response.text
    assert "不能公开的版块" not in response.text
    assert '<a href="/">平行线</a>' in response.text


@pytest.mark.asyncio
async def test_title_suffix_is_limited_to_the_new_forum_root(public_service):
    old = await public_service.forum_page(MAIN)
    new = await public_service.forum_page(FORUM, canonical_path="/")
    old_meta = await public_service.meta_for_path("/forum", MAIN)
    new_meta = await public_service.meta_for_path("/", FORUM, forum_home=True)
    assert old.meta.title == old_meta.title == "平行线 ParallelLines"
    assert new.meta.title == new_meta.title == "平行线 ParallelLines · 圈子"
    assert old.meta.canonical_url == f"{MAIN}/forum"
    assert new.meta.canonical_url == f"{FORUM}/"
