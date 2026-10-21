from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.seo import public_seo_router
from app.services.seo import SeoPageDocument, SeoService, SeoSiteIdentity
from app.services.seo_renderer import render_semantic_fallback


@pytest.fixture
def forum_home(monkeypatch):
    """用公开内容读取替身验证论坛首页，禁止触碰数据库。"""

    class NoDatabaseSession:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected database access: {name}")

    identity = SeoSiteIdentity("平行线", "让答案可追溯", "/logo-lines-mark.png")
    service = SeoService(cast(AsyncSession, NoDatabaseSession()))
    calls = []

    async def read_identity():
        return identity

    async def read_boards(limit):
        calls.append(("boards", limit))
        return [SimpleNamespace(slug="public", name="公开版块", description="公开简介")]

    async def read_topics(limit, **filters):
        calls.append(("topics", limit))
        return [
            SimpleNamespace(
                id="topic-1", slug="public-topic", title="公开主题", reply_count=2, view_count=5
            )
        ]

    monkeypatch.setattr(service, "_site_identity", read_identity)
    monkeypatch.setattr(service, "_public_boards", read_boards)
    monkeypatch.setattr(service, "_public_topics", read_topics)
    return service, identity, calls


def test_forum_home_preserves_old_public_content_with_its_own_canonical(forum_home):
    service, identity, calls = forum_home
    meta = asyncio.run(service.meta_for_path("/forum?sort=latest", "https://pingxingxian.space"))
    assert calls == []

    document = asyncio.run(service.forum_page("https://pingxingxian.space"))
    assert calls == [("boards", 20), ("topics", 20)]
    assert document.meta == meta
    assert meta.canonical_url == meta.og_url == "https://pingxingxian.space/forum"
    assert meta.title == "平行线 ParallelLines"
    assert meta.description == "平行线 ParallelLines：让答案可追溯。浏览公开版块与可追溯讨论。"
    assert document.heading == identity.title
    assert document.intro == meta.description
    assert document.status_code == 200
    assert meta.robots == "index,follow"
    assert [link.path for link in document.links] == ["/b/public", "/topics/topic-1/public-topic"]
    assert document.page_structured_data is None
    assert document.site_structured_data["@graph"][0]["description"] == meta.description

    rendered = render_semantic_fallback(document)
    assert '<a href="/forum">平行线</a>' in rendered
    assert '<a href="/">' not in rendered
    assert '<a href="/b/public">公开版块</a>' in rendered
    assert '<a href="/topics/topic-1/public-topic">公开主题</a>' in rendered


@pytest.mark.parametrize("page", ["boards", "board", "topic", "profile"])
def test_all_public_forum_graphs_match_forum_shell_copy(forum_home, monkeypatch, page):
    service, _, _ = forum_home
    board = SimpleNamespace(
        id="board-1", slug="public", name="公开版块", description="简介", visibility="public"
    )
    topic = SimpleNamespace(
        id="topic-1", slug="public-topic", title="公开主题", reply_count=2,
        view_count=5, deleted_at=None, merged_into_topic_id=None, visibility="public",
        topic_type="regular", status="open", board=board,
    )
    user = SimpleNamespace(
        id="member-1", username="member", display_name="成员", bio="简介",
        status="active", profile_visibility="public", is_persona=True, persona_kind=None,
    )
    monkeypatch.setattr(service, "_board_by_slug", AsyncMock(return_value=board))
    monkeypatch.setattr(service, "_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(service, "_visible_topic_posts", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_post_revision_activity", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(service, "_public_topic_count_for_user", AsyncMock(return_value=0))
    monkeypatch.setattr(service, "_public_post_count_for_user", AsyncMock(return_value=0))
    origin = "https://pingxingxian.space"
    operations = {
        "boards": lambda: service.boards_page(origin),
        "board": lambda: service.board_page("public", origin),
        "topic": lambda: service.topic_page("topic-1", "public-topic", origin),
        "profile": lambda: service.profile_page("member-1", origin),
    }
    document = asyncio.run(operations[page]())
    website, organization = document.site_structured_data["@graph"]
    assert website["description"] == (
        "平行线 ParallelLines：让答案可追溯。浏览公开版块与可追溯讨论。"
    )
    assert website["@id"] == f"{origin}/#website"
    assert organization["@id"] == f"{origin}/#organization"
    assert website["url"] == organization["url"] == f"{origin}/"


def test_forum_home_does_not_expand_sitemap_or_openapi(forum_home):
    service, _, calls = forum_home
    urls = asyncio.run(service.sitemap_urls("https://pingxingxian.space"))
    assert [item.loc for item in urls] == ["https://pingxingxian.space/games"]
    assert calls == []
    route = next(route for route in public_seo_router.routes if route.path == "/forum")
    assert route.include_in_schema is False


@pytest.mark.parametrize(
    ("path", "kind", "home_path"),
    [
        ("/", "home", "/games"),
        ("/games", "home", "/games"),
        ("/tools", "tools", "/games"),
        ("/forum", "home", "/forum"),
        ("/boards", "boards", "/forum"),
        ("/b/public", "board", "/forum"),
        ("/topics/topic-1/public-topic", "topic", "/forum"),
        ("/members/member-1", "profile", "/forum"),
        ("/b/private", "restricted", "/forum"),
        ("/topics/missing", "missing", "/forum"),
        ("/members/private", "restricted", "/forum"),
    ],
)
def test_semantic_navigation_uses_actual_canonical_path(forum_home, path, kind, home_path):
    service, _, _ = forum_home
    original = asyncio.run(service.forum_page("https://pingxingxian.space"))
    document = replace(
        original,
        kind=kind,
        meta=original.meta.model_copy(update={"canonical_url": f"https://pingxingxian.space{path}"}),
        links=(),
    )
    assert isinstance(document, SeoPageDocument)
    rendered = render_semantic_fallback(document)
    assert f'<a href="{home_path}">平行线</a>' in rendered
    if home_path == "/games":
        assert 'href="/forum"' not in rendered
        assert "圈子" not in rendered


@pytest.mark.parametrize(
    "query",
    [b"", b"utm_source=post", b"next=a%2Fb%3Fc%3D1", b"tag=one&tag=two", b"empty="],
)
def test_root_redirect_preserves_query_without_a_database_dependency(query):
    route = next(route for route in public_seo_router.routes if route.path == "/")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": query,
            "server": ("pingxingxian.space", 443),
            "headers": [],
        }
    )
    response = asyncio.run(route.endpoint(request))

    assert route.dependant.dependencies == []
    assert route.include_in_schema is False
    assert response.status_code == 301
    assert response.headers["location"] == "/games" + (
        f"?{query.decode('ascii')}" if query else ""
    )
