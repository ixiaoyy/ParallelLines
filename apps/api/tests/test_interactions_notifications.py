import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.forum import BoardMember, Topic
from app.models.interaction import Bookmark, Notification, Reaction
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "token": data["access_token"],
        "auth": f"Bearer {data['access_token']}",
    }


async def create_topic_fixture(client: AsyncClient, auth: str) -> dict[str, str]:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "support",
            "name": "支持与排障",
            "description": "安装、升级、报错定位，以及可复现问题的协作排查。",
            "color": "#10B981",
        },
    )
    assert board.status_code == 201

    topic = await client.post(
        "/api/v1/boards/support/topics",
        headers={"Authorization": auth},
        json={
            "title": "FastAPI 长任务通知如何设计？",
            "raw_md": "想知道回复、提及和关注版块通知应该如何落库。",
            "tags": ["fastapi", "notifications"],
        },
    )
    assert topic.status_code == 201
    topic_data = topic.json()["data"]

    posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts")
    assert posts.status_code == 200
    first_post = posts.json()["data"][0]

    return {"topic_id": topic_data["id"], "post_id": first_post["id"]}


@pytest.mark.asyncio
async def test_follow_like_and_bookmark_are_idempotent() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        member = await register_user(client, "member")
        fixture = await create_topic_fixture(client, owner["auth"])
        member_headers = {"Authorization": member["auth"]}

        follow = await client.put(
            "/api/v1/boards/support/follow",
            headers=member_headers,
            json={"notification_level": "watching"},
        )
        repeat_follow = await client.put(
            "/api/v1/boards/support/follow",
            headers=member_headers,
            json={"notification_level": "watching"},
        )
        assert follow.status_code == 200
        assert repeat_follow.status_code == 200
        assert repeat_follow.json()["data"]["follower_count"] == 2

        like = await client.put(f"/api/v1/posts/{fixture['post_id']}/like", headers=member_headers)
        repeat_like = await client.put(
            f"/api/v1/posts/{fixture['post_id']}/like", headers=member_headers
        )
        assert like.status_code == 200
        assert repeat_like.status_code == 200
        assert repeat_like.json()["data"] == {
            "target_type": "post",
            "target_id": fixture["post_id"],
            "active": True,
            "count": 1,
        }

        bookmark = await client.put(
            f"/api/v1/topics/{fixture['topic_id']}/bookmark",
            headers=member_headers,
        )
        repeat_bookmark = await client.put(
            f"/api/v1/topics/{fixture['topic_id']}/bookmark",
            headers=member_headers,
        )
        assert bookmark.status_code == 200
        assert repeat_bookmark.status_code == 200
        assert repeat_bookmark.json()["data"]["count"] == 1

        topic = await client.get(f"/api/v1/topics/{fixture['topic_id']}")
        assert topic.status_code == 200
        assert topic.json()["data"]["like_count"] == 1

        unlike = await client.delete(
            f"/api/v1/posts/{fixture['post_id']}/like", headers=member_headers
        )
        unbookmark = await client.delete(
            f"/api/v1/topics/{fixture['topic_id']}/bookmark",
            headers=member_headers,
        )
        unfollow = await client.delete("/api/v1/boards/support/follow", headers=member_headers)
        assert unlike.status_code == 200
        assert unlike.json()["data"]["count"] == 0
        assert unbookmark.status_code == 200
        assert unbookmark.json()["data"]["count"] == 0
        assert unfollow.status_code == 200
        assert unfollow.json()["data"]["follower_count"] == 1

    async with session_factory() as session:
        reaction_count = await session.scalar(select(func.count(Reaction.id)))
        bookmark_count = await session.scalar(select(func.count(Bookmark.id)))
        member_count = await session.scalar(select(func.count(BoardMember.id)))
        assert reaction_count == 0
        assert bookmark_count == 0
        assert member_count == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_reply_and_board_follow_create_readable_notifications() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        watcher = await register_user(client, "watcher")
        fixture = await create_topic_fixture(client, owner["auth"])
        watcher_headers = {"Authorization": watcher["auth"]}
        owner_headers = {"Authorization": owner["auth"]}

        follow = await client.put(
            "/api/v1/boards/support/follow",
            headers=watcher_headers,
            json={"notification_level": "watching"},
        )
        assert follow.status_code == 200

        new_topic = await client.post(
            "/api/v1/boards/support/topics",
            headers=owner_headers,
            json={
                "title": "关注版块后是否收到新主题通知？",
                "raw_md": "这个主题用于验证 board_new_topic 通知。",
                "tags": ["notification"],
            },
        )
        assert new_topic.status_code == 201

        watcher_notifications = await client.get(
            "/api/v1/notifications",
            headers=watcher_headers,
        )
        assert watcher_notifications.status_code == 200
        watcher_data = watcher_notifications.json()["data"]
        assert watcher_data["unread_count"] == 1
        assert watcher_data["notifications"][0]["type"] == "board_new_topic"

        reply = await client.post(
            f"/api/v1/topics/{fixture['topic_id']}/posts",
            headers=watcher_headers,
            json={"raw_md": "@owner 我复现了这个通知路径。"},
        )
        assert reply.status_code == 201

        owner_notifications = await client.get("/api/v1/notifications", headers=owner_headers)
        assert owner_notifications.status_code == 200
        owner_data = owner_notifications.json()["data"]
        notification_types = {item["type"] for item in owner_data["notifications"]}
        assert owner_data["unread_count"] >= 1
        assert {"replied", "mentioned"}.issubset(notification_types)

        stream = await client.get(
            "/api/v1/notifications/stream?once=true&poll_seconds=1",
            headers=owner_headers,
        )
        assert stream.status_code == 200
        assert "event: notifications" in stream.text
        assert f'"unread_count":{owner_data["unread_count"]}' in stream.text

        mark_read = await client.put(
            "/api/v1/notifications/read",
            headers=owner_headers,
            json={},
        )
        assert mark_read.status_code == 200
        assert mark_read.json()["data"]["updated_count"] >= 1
        assert mark_read.json()["data"]["unread_count"] == 0

    async with session_factory() as session:
        topic_count = await session.scalar(select(func.count(Topic.id)))
        notification_count = await session.scalar(select(func.count(Notification.id)))
        assert topic_count == 2
        assert notification_count >= 3

    await engine.dispose()
