import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.forum import Topic
from app.models.search import SearchDocument, SearchLog
from app.workers.background_jobs import recompute_hot_scores
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient) -> str:
    response = await register_and_verify_user(client, "searcher", email="searcher@example.com")
    return f"Bearer {response['access_token']}"


async def create_board(client: AsyncClient, auth: str, slug: str, name: str) -> None:
    response = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": slug,
            "name": name,
            "description": f"{name} 的可搜索主题。",
            "color": "#409EFF",
        },
    )
    assert response.status_code == 201


async def create_topic(
    client: AsyncClient,
    auth: str,
    board_slug: str,
    title: str,
    raw_md: str,
    tags: list[str],
) -> str:
    response = await client.post(
        f"/api/v1/boards/{board_slug}/topics",
        headers={"Authorization": auth},
        json={"title": title, "raw_md": raw_md, "tags": tags},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_search_filters_cursor_and_hot_recompute() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        auth = await register_user(client)
        headers = {"Authorization": auth}
        await create_board(client, auth, "support", "支持与排障")
        await create_board(client, auth, "dev", "开发与 API")

        oidc_topic_id = await create_topic(
            client,
            auth,
            "support",
            "OIDC 登录回跳首页如何排查？",
            "Edge callback 日志里出现 state mismatch。",
            ["oidc", "登录"],
        )
        timeout_topic_id = await create_topic(
            client,
            auth,
            "dev",
            "CSV 导入 API timeout 怎么拆队列？",
            "导入 2 万行时 API timeout，但后台最终成功。",
            ["csv", "queue"],
        )
        callback_title_topic_id = await create_topic(
            client,
            auth,
            "support",
            "Callback 参数校验指南",
            "这条主题把关键词放在标题中，应该比正文命中更靠前。",
            ["oidc"],
        )
        special_topic_id = await create_topic(
            client,
            auth,
            "support",
            "字面量 100%_token 查询",
            "特殊字符不能被当作 LIKE 通配符。",
            ["literal"],
        )
        old_marker_topic_id = await create_topic(
            client,
            auth,
            "support",
            "索引更新主题",
            "old-marker 只在旧正文里出现。",
            ["sync"],
        )

        search = await client.get("/api/v1/search?q=callback")
        assert search.status_code == 200
        assert search.headers["x-parallellines-cache"] == "miss"
        assert [item["id"] for item in search.json()["data"][:2]] == [
            callback_title_topic_id,
            oidc_topic_id,
        ]

        cached_search = await client.get("/api/v1/search?q=callback")
        assert cached_search.status_code == 200
        assert cached_search.headers["x-parallellines-cache"] == "hit"
        assert [item["id"] for item in cached_search.json()["data"][:2]] == [
            callback_title_topic_id,
            oidc_topic_id,
        ]

        literal = await client.get("/api/v1/search", params={"q": "100%_token"})
        assert literal.status_code == 200
        assert [item["id"] for item in literal.json()["data"]] == [special_topic_id]

        tag_filter = await client.get("/api/v1/topics?tag=csv")
        assert tag_filter.status_code == 200
        assert [item["id"] for item in tag_filter.json()["data"]] == [timeout_topic_id]

        pinned = await client.put(
            f"/api/v1/topics/{oidc_topic_id}/lifecycle",
            headers=headers,
            json={"pinned": True},
        )
        assert pinned.status_code == 200
        board_latest = await client.get(
            "/api/v1/boards/support/topics", params={"sort": "latest"}
        )
        assert board_latest.status_code == 200
        assert board_latest.json()["data"][0]["id"] == oidc_topic_id
        assert board_latest.json()["data"][0]["pinned"] is True

        first_page = await client.get("/api/v1/topics?limit=1")
        assert first_page.status_code == 200
        assert first_page.json()["data"][0]["id"] == oidc_topic_id
        assert first_page.json()["meta"]["next_cursor"] is not None

        second_page = await client.get(
            "/api/v1/topics",
            params={"limit": 1, "cursor": first_page.json()["meta"]["next_cursor"]},
        )
        assert second_page.status_code == 200
        assert second_page.json()["data"][0]["id"] != first_page.json()["data"][0]["id"]
        assert second_page.json()["data"][0]["pinned"] is False

        reply = await client.post(
            f"/api/v1/topics/{oidc_topic_id}/posts",
            headers=headers,
            json={"raw_md": "补充一个复现路径，确认这条主题更热。"},
        )
        assert reply.status_code == 201

        close = await client.put(
            f"/api/v1/topics/{callback_title_topic_id}/lifecycle",
            headers=headers,
            json={"status": "closed"},
        )
        assert close.status_code == 200
        closed_search = await client.get("/api/v1/search?q=callback&status=closed")
        assert closed_search.status_code == 200
        assert [item["id"] for item in closed_search.json()["data"]] == [callback_title_topic_id]

        posts = await client.get(f"/api/v1/topics/{old_marker_topic_id}/posts")
        assert posts.status_code == 200
        first_post_id = posts.json()["data"][0]["id"]
        update = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers=headers,
            json={"raw_md": "new-marker 是更新后的正文。", "edit_reason": "sync test"},
        )
        assert update.status_code == 200
        old_search = await client.get("/api/v1/search?q=old-marker")
        assert old_search.status_code == 200
        assert old_marker_topic_id not in {item["id"] for item in old_search.json()["data"]}
        new_search = await client.get("/api/v1/search?q=new-marker")
        assert new_search.status_code == 200
        assert [item["id"] for item in new_search.json()["data"]] == [old_marker_topic_id]

    async with session_factory() as session:
        indexed_count = await session.scalar(select(func.count(SearchDocument.id)))
        assert indexed_count == 5
        log_count = await session.scalar(select(func.count(SearchLog.id)))
        assert log_count is not None and log_count >= 5

        timeout_topic = await session.get(Topic, timeout_topic_id)
        assert timeout_topic is not None
        timeout_topic.view_count = 2000
        timeout_topic.like_count = 10
        await session.commit()
        updated_count = await recompute_hot_scores(session)
        assert updated_count == 5

        hot_topics = list(await session.scalars(select(Topic).order_by(Topic.hot_score.desc())))
        assert hot_topics[0].id == timeout_topic_id
        assert hot_topics[0].hot_score > hot_topics[1].hot_score

    await engine.dispose()
