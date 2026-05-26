"""Test suite for notification preferences, muted topics, and quiet hours.

Covers:
- muted topic suppresses replied/mentioned/liked notifications
- watching topic level generates topic_new_post notification
- GET/PUT /topics/{id}/notification-level API
- quiet hours suppresses email sending
"""
from __future__ import annotations

from datetime import UTC
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.models.forum import TopicRead
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


async def setup_board_and_topic(
    client: AsyncClient, owner_auth: str
) -> dict[str, str]:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": owner_auth},
        json={
            "slug": "general",
            "name": "综合讨论",
            "description": "通用讨论版块",
            "color": "#409EFF",
        },
    )
    assert board.status_code == 201

    topic = await client.post(
        "/api/v1/boards/general/topics",
        headers={"Authorization": owner_auth},
        json={
            "title": "测试通知偏好",
            "raw_md": "这是第一楼，用于测试通知偏好矩阵。",
            "tags": ["test"],
        },
    )
    assert topic.status_code == 201
    topic_data = topic.json()["data"]

    posts = await client.get(f"/api/v1/topics/{topic_data['id']}/posts")
    assert posts.status_code == 200
    first_post = posts.json()["data"][0]

    return {
        "topic_id": topic_data["id"],
        "post_id": first_post["id"],
        "board_slug": "general",
    }


@pytest.mark.asyncio
async def test_muted_topic_suppresses_replied_notification() -> None:
    """When a topic is muted, reply notifications are suppressed."""
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner_muted")
        replier = await register_user(client, "replier_muted")
        fixture = await setup_board_and_topic(client, owner["auth"])
        topic_id = fixture["topic_id"]

        # Owner mutes their own topic
        mute_resp = await client.put(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": owner["auth"]},
            json={"notification_level": "muted"},
        )
        assert mute_resp.status_code == 200
        assert mute_resp.json()["data"]["notification_level"] == "muted"

        # Replier posts a reply and mentions the muted owner.
        reply = await client.post(
            f"/api/v1/topics/{topic_id}/posts",
            headers={"Authorization": replier["auth"]},
            json={"raw_md": "这是一条回复，@owner_muted 应该看不到通知。"},
        )
        assert reply.status_code == 201

        like = await client.put(
            f"/api/v1/posts/{fixture['post_id']}/like",
            headers={"Authorization": replier["auth"]},
        )
        assert like.status_code == 200
        await drain_background_jobs(session_factory)

        # Owner should have NO notifications (muted suppresses replied/mentioned/liked)
        notifs = await client.get("/api/v1/notifications", headers={"Authorization": owner["auth"]})
        assert notifs.status_code == 200
        owner_notif_data = notifs.json()["data"]
        assert owner_notif_data["unread_count"] == 0
        notification_types = [n["type"] for n in owner_notif_data["notifications"]]
        assert "replied" not in notification_types
        assert "mentioned" not in notification_types
        assert "liked" not in notification_types

    await engine.dispose()


@pytest.mark.asyncio
async def test_watching_topic_generates_topic_new_post_notification() -> None:
    """When a user sets watching on a topic, they get topic_new_post for all new replies."""
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner_watch")
        watcher = await register_user(client, "watcher_watch")
        fixture = await setup_board_and_topic(client, owner["auth"])
        topic_id = fixture["topic_id"]

        # Watcher explicitly sets watching
        watch_resp = await client.put(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": watcher["auth"]},
            json={"notification_level": "watching"},
        )
        assert watch_resp.status_code == 200

        # Owner posts a new reply
        reply = await client.post(
            f"/api/v1/topics/{topic_id}/posts",
            headers={"Authorization": owner["auth"]},
            json={"raw_md": "Owner 添加了一条新回复。"},
        )
        assert reply.status_code == 201
        await drain_background_jobs(session_factory)

        # Watcher should have a topic_new_post notification
        notifs = await client.get(
            "/api/v1/notifications", headers={"Authorization": watcher["auth"]}
        )
        assert notifs.status_code == 200
        watcher_data = notifs.json()["data"]
        assert watcher_data["unread_count"] >= 1
        notification_types = [n["type"] for n in watcher_data["notifications"]]
        assert "topic_new_post" in notification_types

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_and_set_topic_notification_level_api() -> None:
    """GET returns current level; PUT changes it and persists."""
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "user_level")
        owner = await register_user(client, "owner_level")
        fixture = await setup_board_and_topic(client, owner["auth"])
        topic_id = fixture["topic_id"]

        # GET when no record exists → normal
        get_resp = await client.get(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": user["auth"]},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["notification_level"] == "normal"
        assert get_resp.json()["data"]["topic_id"] == topic_id

        # PUT → muted
        put_resp = await client.put(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": user["auth"]},
            json={"notification_level": "muted"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["data"]["notification_level"] == "muted"

        # GET reflects the change
        get_resp2 = await client.get(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": user["auth"]},
        )
        assert get_resp2.status_code == 200
        assert get_resp2.json()["data"]["notification_level"] == "muted"

        # PUT → watching
        put_resp2 = await client.put(
            f"/api/v1/topics/{topic_id}/notification-level",
            headers={"Authorization": user["auth"]},
            json={"notification_level": "watching"},
        )
        assert put_resp2.status_code == 200
        assert put_resp2.json()["data"]["notification_level"] == "watching"

    # Verify persistence in DB
    async with session_factory() as session:
        read_state = await session.scalar(
            select(TopicRead).where(
                TopicRead.topic_id == topic_id,
            )
        )
        # At least one TopicRead for this topic should exist
        assert read_state is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_quiet_hours_suppress_email() -> None:
    """Email is suppressed when sent within the user's quiet hours window."""
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "quiet_user")

        # Set quiet hours: 0–23 (all day = always suppressed)
        pref_resp = await client.put(
            "/api/v1/email/preferences",
            headers={"Authorization": user["auth"]},
            json={
                "email_enabled": True,
                "notify_replied": True,
                "quiet_hours_start": 0,
                "quiet_hours_end": 23,
            },
        )
        assert pref_resp.status_code == 200
        pref_data = pref_resp.json()["data"]
        assert pref_data["quiet_hours_start"] == 0
        assert pref_data["quiet_hours_end"] == 23

        # Verify _can_send_notification_email returns False
        async with session_factory() as session:
            from app.models.user import User
            from app.services.email_notifications import EmailNotificationService

            db_user = await session.scalar(
                select(User).where(User.username == "quiet_user")
            )
            assert db_user is not None

            svc = EmailNotificationService(session)
            # With quiet hours 0-23 covering current hour, email should be suppressed
            # We mock utcnow to return a fixed hour within the window (e.g., hour=5)
            from datetime import datetime

            from app.db import base as base_module

            def mock_utcnow():
                return datetime(2025, 1, 1, 5, 0, 0, tzinfo=UTC)

            with patch.object(base_module, "utcnow", mock_utcnow):
                # Also patch in the email_notifications module's import
                import app.services.email_notifications as email_module
                with patch.object(email_module, "utcnow", mock_utcnow):
                    can_send = await svc._can_send_notification_email(db_user.id, "replied")
                    assert can_send is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_quiet_hours_wrapping_midnight() -> None:
    """Quiet hours that span midnight (e.g. 22-06) correctly suppress at hour 2."""
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_user(client, "midnight_user")

        # Set quiet hours: 22-06 (wraps midnight)
        await client.put(
            "/api/v1/email/preferences",
            headers={"Authorization": user["auth"]},
            json={
                "email_enabled": True,
                "notify_replied": True,
                "quiet_hours_start": 22,
                "quiet_hours_end": 6,
            },
        )

    async with session_factory() as session:
        from datetime import datetime

        from app.models.user import User
        from app.services.email_notifications import EmailNotificationService

        db_user = await session.scalar(
            select(User).where(User.username == "midnight_user")
        )
        assert db_user is not None
        svc = EmailNotificationService(session)

        import app.services.email_notifications as email_module

        # Hour 2 = inside quiet window (22-06 wraps midnight)
        def mock_utcnow_2am():
            return datetime(2025, 1, 1, 2, 0, 0, tzinfo=UTC)

        with patch.object(email_module, "utcnow", mock_utcnow_2am):
            can_send_2am = await svc._can_send_notification_email(db_user.id, "replied")

        # Hour 14 = outside quiet window
        def mock_utcnow_2pm():
            return datetime(2025, 1, 1, 14, 0, 0, tzinfo=UTC)

        with patch.object(email_module, "utcnow", mock_utcnow_2pm):
            can_send_2pm = await svc._can_send_notification_email(db_user.id, "replied")

        assert can_send_2am is False, "Hour 2 should be in quiet window (22-06)"
        assert can_send_2pm is True, "Hour 14 should be outside quiet window"

    await engine.dispose()
