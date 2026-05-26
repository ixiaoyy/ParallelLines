import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.interaction import Notification
from app.models.social import PrivateMessageParticipant, UserRelationship
from tests.helpers import (
    drain_background_jobs,
    get_test_database_url,
    register_and_verify_user,
    reset_test_database,
)


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "token": data["access_token"],
        "auth": f"Bearer {data['access_token']}",
    }


async def create_board(client: AsyncClient, auth: str, slug: str) -> None:
    response = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": slug,
            "name": f"{slug} 版块",
            "description": "用于用户关系和通知测试的公开版块。",
            "color": "#409EFF",
        },
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_followed_user_topic_notification_and_block_suppression() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        author = await register_user(client, "followed_author")
        follower = await register_user(client, "topic_follower")
        await create_board(client, author["auth"], "social-follow")

        follow = await client.put(
            "/api/v1/users/followed_author/follow",
            headers={"Authorization": follower["auth"]},
        )
        assert follow.status_code == 200
        assert follow.json()["data"]["following"] is True

        topic = await client.post(
            "/api/v1/boards/social-follow/topics",
            headers={"Authorization": author["auth"]},
            json={"title": "关注作者后的第一条主题", "raw_md": "关注者应该收到动态通知。"},
        )
        assert topic.status_code == 201
        await drain_background_jobs(session_factory)

        notifications = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": follower["auth"]},
        )
        assert notifications.status_code == 200
        first_types = [item["type"] for item in notifications.json()["data"]["notifications"]]
        assert "user_new_topic" in first_types

        block = await client.put(
            "/api/v1/users/followed_author/block",
            headers={"Authorization": follower["auth"]},
        )
        assert block.status_code == 200
        assert block.json()["data"]["blocked"] is True
        assert block.json()["data"]["following"] is False

        second_topic = await client.post(
            "/api/v1/boards/social-follow/topics",
            headers={"Authorization": author["auth"]},
            json={"title": "被屏蔽后的主题", "raw_md": "屏蔽后不应继续产生作者动态通知。"},
        )
        assert second_topic.status_code == 201
        await drain_background_jobs(session_factory)

        notifications_after_block = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": follower["auth"]},
        )
        assert notifications_after_block.status_code == 200
        user_topic_count = sum(
            1
            for item in notifications_after_block.json()["data"]["notifications"]
            if item["type"] == "user_new_topic"
        )
        assert user_topic_count == 1

    async with session_factory() as session:
        relationship_count = await session.scalar(select(func.count(UserRelationship.id)))
        assert relationship_count == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_private_message_topic_is_participant_only_and_notifies_replies() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sender = await register_user(client, "pm_sender")
        recipient = await register_user(client, "pm_recipient")
        stranger = await register_user(client, "pm_stranger")

        created = await client.post(
            "/api/v1/users/messages",
            headers={"Authorization": sender["auth"]},
            json={
                "participant_usernames": ["pm_recipient"],
                "title": "私信协作主题",
                "raw_md": "这是一条只允许参与者阅读的私信。",
            },
        )
        assert created.status_code == 201
        message = created.json()["data"]
        topic_id = message["topic"]["id"]
        assert message["topic"]["visibility"] == "private_message"
        assert {item["username"] for item in message["participants"]} == {
            "pm_sender",
            "pm_recipient",
        }

        recipient_topic = await client.get(
            f"/api/v1/topics/{topic_id}",
            headers={"Authorization": recipient["auth"]},
        )
        assert recipient_topic.status_code == 200

        stranger_topic = await client.get(
            f"/api/v1/topics/{topic_id}",
            headers={"Authorization": stranger["auth"]},
        )
        assert stranger_topic.status_code == 404

        stranger_posts = await client.get(
            f"/api/v1/topics/{topic_id}/posts",
            headers={"Authorization": stranger["auth"]},
        )
        assert stranger_posts.status_code == 404

        reply = await client.post(
            f"/api/v1/topics/{topic_id}/posts",
            headers={"Authorization": recipient["auth"]},
            json={"raw_md": "收到，我会继续在私信里补充上下文。"},
        )
        assert reply.status_code == 201
        await drain_background_jobs(session_factory)

        sender_notifications = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": sender["auth"]},
        )
        assert sender_notifications.status_code == 200
        notification_types = {
            item["type"] for item in sender_notifications.json()["data"]["notifications"]
        }
        assert "private_message" in notification_types

        recipient_messages = await client.get(
            "/api/v1/users/messages",
            headers={"Authorization": recipient["auth"]},
        )
        assert recipient_messages.status_code == 200
        assert recipient_messages.json()["data"][0]["topic"]["id"] == topic_id

    async with session_factory() as session:
        participant_count = await session.scalar(select(func.count(PrivateMessageParticipant.id)))
        notification_count = await session.scalar(select(func.count(Notification.id)))
        assert participant_count == 2
        assert notification_count >= 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_private_message_creation_respects_block_boundary() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocker = await register_user(client, "pm_blocker")
        blocked = await register_user(client, "pm_blocked")

        block = await client.put(
            "/api/v1/users/pm_blocked/block",
            headers={"Authorization": blocker["auth"]},
        )
        assert block.status_code == 200

        created = await client.post(
            "/api/v1/users/messages",
            headers={"Authorization": blocked["auth"]},
            json={
                "participant_usernames": ["pm_blocker"],
                "title": "越过屏蔽边界的私信",
                "raw_md": "这条私信应该被拒绝。",
            },
        )
        assert created.status_code == 422
        assert created.json()["error"]["code"] == "private_message_blocked"

    await engine.dispose()
