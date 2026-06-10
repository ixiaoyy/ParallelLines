import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.forum import Board, Post, Topic, TopicRead, TopicView
from app.models.user import User
from app.schemas.forum import BoardCreateRequest, PostCreateRequest, TopicCreateRequest
from app.services.forum import ForumService
from app.services.quality_posts import QUALITY_POST_SPECS, sync_quality_posts
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.asyncio
async def test_forum_api_happy_path() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "lina", email="lina@example.com")
        headers = {"Authorization": f"Bearer {user['access_token']}"}

        board = await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "support",
                "name": "支持与排障",
                "description": "安装、升级、报错定位，以及可复现问题的协作排查。",
                "color": "#10B981",
            },
        )
        assert board.status_code == 201
        assert board.json()["data"]["topic_count"] == 0
        assert board.json()["data"]["follower_count"] == 1

        topic = await client.post(
            "/api/v1/boards/support/topics",
            headers=headers,
            json={
                "title": "FastAPI 长任务：先上队列还是 Celery？",
                "raw_md": """环境：Windows 11

```python
print('<script>')
```""",
                "tags": ["fastapi", "队列"],
            },
        )
        assert topic.status_code == 201
        topic_data = topic.json()["data"]
        assert topic_data["board_slug"] == "support"
        assert topic_data["reply_count"] == 0
        assert topic_data["tags"] == ["fastapi", "队列"]

        posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts")
        assert posts.status_code == 200
        assert posts.headers["x-parallellines-cache"] == "miss"
        post_data = posts.json()["data"][0]
        assert post_data["post_number"] == 1
        assert "&lt;script&gt;" in post_data["cooked_html"]
        assert "<script>" not in post_data["cooked_html"]

        cached_posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts")
        assert cached_posts.status_code == 200
        assert cached_posts.headers["x-parallellines-cache"] == "hit"

        immersive_feed = await client.get("/api/v1/topics/immersive-feed")
        assert immersive_feed.status_code == 200
        assert immersive_feed.headers["x-parallellines-cache"] == "miss"

        cached_immersive_feed = await client.get("/api/v1/topics/immersive-feed")
        assert cached_immersive_feed.status_code == 200
        assert cached_immersive_feed.headers["x-parallellines-cache"] == "hit"

        reply = await client.post(
            f"/api/v1/topics/{topic_data['id']}/posts",
            headers=headers,
            json={"raw_md": "我也复现了，后台 worker 重启后状态会卡住。"},
        )
        assert reply.status_code == 201
        assert reply.json()["data"]["post_number"] == 2

        refreshed_posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts")
        assert refreshed_posts.status_code == 200
        assert refreshed_posts.headers["x-parallellines-cache"] == "miss"
        assert len(refreshed_posts.json()["data"]) == 2

        topic_after_reply = await client.get(f"/api/v1/topics/{topic_data['id']}")
        assert topic_after_reply.status_code == 200
        assert topic_after_reply.json()["data"]["reply_count"] == 1

        board_detail = await client.get("/api/v1/boards/support")
        assert board_detail.status_code == 200
        board_data = board_detail.json()["data"]
        assert board_data["topic_count"] == 1
        assert board_data["post_count"] == 2
        assert board_data["latest_topics"][0]["id"] == topic_data["id"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_topic_detail_counts_one_view_per_viewer() -> None:
    """Verify topic detail views are counted once per logged-in or anonymous viewer."""

    session_factory, engine = await create_test_session()

    async def override_session():
        """Yield isolated test DB sessions for this ASGI app instance."""

        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "viewer", email="viewer@example.com")
        headers = {"Authorization": f"Bearer {user['access_token']}"}

        board = await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "views",
                "name": "浏览计数",
                "description": "用于验证主题浏览数去重。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        topic = await client.post(
            "/api/v1/boards/views/topics",
            headers=headers,
            json={"title": "浏览数只应按人计一次", "raw_md": "重复打开详情页不应重复累加。"},
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        posts = await client.get(f"/api/v1/topics/{topic_id}/posts", headers=headers)
        assert posts.status_code == 200
        async with session_factory() as session:
            saved_topic = await session.get(Topic, topic_id)
            assert saved_topic is not None
            assert saved_topic.view_count == 0

        first_view = await client.get(f"/api/v1/topics/{topic_id}", headers=headers)
        assert first_view.status_code == 200
        assert first_view.json()["data"]["view_count"] == 1

        repeated_view = await client.get(f"/api/v1/topics/{topic_id}", headers=headers)
        assert repeated_view.status_code == 200
        assert repeated_view.json()["data"]["view_count"] == 1

        other_user = await register_and_verify_user(client, "other_viewer")
        other_headers = {"Authorization": f"Bearer {other_user['access_token']}"}
        other_view = await client.get(f"/api/v1/topics/{topic_id}", headers=other_headers)
        assert other_view.status_code == 200
        assert other_view.json()["data"]["view_count"] == 2

        anonymous_headers = {"X-ParallelLines-Visitor": "visitor-browser-a"}
        anonymous_view = await client.get(f"/api/v1/topics/{topic_id}", headers=anonymous_headers)
        assert anonymous_view.status_code == 200
        assert anonymous_view.json()["data"]["view_count"] == 3

        repeated_anonymous_view = await client.get(
            f"/api/v1/topics/{topic_id}",
            headers=anonymous_headers,
        )
        assert repeated_anonymous_view.status_code == 200
        assert repeated_anonymous_view.json()["data"]["view_count"] == 3

        second_anonymous_view = await client.get(
            f"/api/v1/topics/{topic_id}",
            headers={"X-ParallelLines-Visitor": "visitor-browser-b"},
        )
        assert second_anonymous_view.status_code == 200
        assert second_anonymous_view.json()["data"]["view_count"] == 4

        unidentified_anonymous_view = await client.get(f"/api/v1/topics/{topic_id}")
        assert unidentified_anonymous_view.status_code == 200
        assert unidentified_anonymous_view.json()["data"]["view_count"] == 4

        async with session_factory() as session:
            saved_topic = await session.get(Topic, topic_id)
            view_rows = await session.scalar(
                select(func.count(TopicView.id)).where(TopicView.topic_id == topic_id)
            )
            assert saved_topic is not None
            assert saved_topic.view_count == 4
            assert view_rows == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_forum_service_updates_counters_and_read_state() -> None:
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        user = User(username="moss", email="moss@example.com", hashed_password="hashed")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        service = ForumService(session)
        board = await service.create_board(
            BoardCreateRequest(
                slug="dev",
                name="开发与 API",
                description="FastAPI、Vue、OpenAPI、权限模型与扩展开发讨论。",
                color="#F59E0B",
            ),
            user,
        )
        topic = await service.create_topic(
            board.slug,
            TopicCreateRequest(
                title="OpenAPI client 生成后枚举命名不稳定",
                raw_md="生成后的枚举每次顺序都不同，需要固定排序。",
                tags=["openapi", "api"],
            ),
            user,
        )
        reply = await service.reply_to_topic(
            topic.id,
            PostCreateRequest(raw_md="可以在 schema 输出前统一排序。"),
            user,
        )

        saved_board = await session.get(Board, board.id)
        saved_topic = await session.get(Topic, topic.id)
        read_state = await session.scalar(
            select(TopicRead).where(TopicRead.topic_id == topic.id, TopicRead.user_id == user.id)
        )
        post_count = await session.scalar(
            select(func.count(Post.id)).where(Post.topic_id == topic.id)
        )

        assert saved_board is not None
        assert saved_board.topic_count == 1
        assert saved_board.post_count == 2
        assert saved_topic is not None
        assert saved_topic.reply_count == 1
        assert saved_topic.last_posted_at is not None
        assert reply.post_number == 2
        assert post_count == 2
        assert read_state is not None
        assert read_state.last_read_post_number == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_sync_quality_posts_writes_official_topics_without_pin() -> None:
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        user = User(
            username="official_author",
            email="official_author@example.com",
            hashed_password="hashed",
            role="admin",
        )
        other_user = User(
            username="other_user",
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        session.add_all([user, other_user])
        await session.commit()
        await session.refresh(user)
        await session.refresh(other_user)

        service = ForumService(session)
        board = await service.create_board(
            BoardCreateRequest(
                slug="announcements",
                name="公告与更新",
                description="版本发布、维护窗口、路线图和社区规则更新。",
                color="#409EFF",
            ),
            user,
        )

        first_sync = await sync_quality_posts(session)
        first_topic_post = await session.scalar(
            select(Post).where(Post.topic_id == first_sync[0].id, Post.post_number == 1)
        )
        assert first_topic_post is not None
        first_sync[0].user_id = other_user.id
        first_topic_post.user_id = other_user.id
        await session.commit()

        second_sync = await sync_quality_posts(session)

        topic_count = await session.scalar(select(func.count(Topic.id)))
        post_count = await session.scalar(select(func.count(Post.id)))
        saved_board = await session.get(Board, board.id)
        migrated_first_post = await session.scalar(
            select(Post).where(Post.topic_id == first_sync[0].id, Post.post_number == 1)
        )

        assert len(first_sync) == len(QUALITY_POST_SPECS)
        assert [topic.id for topic in second_sync] == [topic.id for topic in first_sync]
        assert topic_count == len(QUALITY_POST_SPECS)
        assert post_count == len(QUALITY_POST_SPECS)
        assert saved_board is not None
        assert saved_board.topic_count == len(QUALITY_POST_SPECS)
        assert migrated_first_post is not None
        assert migrated_first_post.user_id == user.id

        for topic in second_sync:
            assert topic.pinned is False
            assert topic.featured is True
            assert topic.user_id == user.id

    await engine.dispose()
