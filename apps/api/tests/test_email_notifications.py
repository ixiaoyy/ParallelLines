import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.services.background_jobs import BackgroundJobService
from app.services.email import EMAIL_OUTBOX, clear_email_outbox
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
    data = await register_and_verify_user(client, username, email=f"{username}@example.com")
    return {
        "id": data["user"]["id"],
        "email": data["user"]["email"],
        "auth": f"Bearer {data['access_token']}",
    }


async def create_topic(client: AsyncClient, auth: str) -> dict[str, str]:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "mail-board",
            "name": "邮件通知",
            "description": "用于验证邮件通知的版块。",
            "color": "#409EFF",
        },
    )
    assert board.status_code == 201
    topic = await client.post(
        "/api/v1/boards/mail-board/topics",
        headers={"Authorization": auth},
        json={
            "title": "邮件提醒如何避免打扰？",
            "raw_md": "需要验证回复、提及和摘要邮件。",
            "tags": ["email"],
        },
    )
    assert topic.status_code == 201
    return {"id": topic.json()["data"]["id"], "slug": topic.json()["data"]["slug"]}


@pytest.mark.asyncio
async def test_reply_notification_email_respects_user_preferences() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "mailowner")
        replier = await register_user(client, "mailreply")
        await drain_background_jobs(session_factory)
        clear_email_outbox()

        topic = await create_topic(client, owner["auth"])
        reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": replier["auth"]},
            json={"raw_md": "我来回复并触发邮件通知。"},
        )
        assert reply.status_code == 201
        await drain_background_jobs(session_factory)

        replied_emails = [email for email in EMAIL_OUTBOX if email.kind == "notification_replied"]
        assert len(replied_emails) == 1
        assert replied_emails[0].to_email == owner["email"]
        assert "邮件提醒如何避免打扰" in replied_emails[0].body

        preferences = await client.put(
            "/api/v1/email/preferences",
            headers={"Authorization": owner["auth"]},
            json={"notify_replied": False},
        )
        assert preferences.status_code == 200
        assert preferences.json()["data"]["notify_replied"] is False

        second_reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": replier["auth"]},
            json={"raw_md": "关闭回复邮件后不应再发。"},
        )
        assert second_reply.status_code == 201
        await drain_background_jobs(session_factory)
        assert len([email for email in EMAIL_OUTBOX if email.kind == "notification_replied"]) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_digest_job_sends_only_due_active_users() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "digestowner")
        replier = await register_user(client, "digestreply")
        await drain_background_jobs(session_factory)
        clear_email_outbox()
        topic = await create_topic(client, owner["auth"])
        reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": replier["auth"]},
            json={"raw_md": "这条通知会进入摘要。"},
        )
        assert reply.status_code == 201
        await drain_background_jobs(session_factory)
        clear_email_outbox()

        async with session_factory() as session:
            await BackgroundJobService(session).enqueue(
                "send_digest_emails",
                queue="mail",
                idempotency_key="test:digest:once",
            )
        await drain_background_jobs(session_factory)

        digest_emails = [email for email in EMAIL_OUTBOX if email.kind == "email_digest"]
        assert len(digest_emails) == 1
        assert digest_emails[0].to_email == owner["email"]
        assert "每日摘要" in digest_emails[0].subject

    await engine.dispose()


@pytest.mark.asyncio
async def test_delivery_and_inbound_webhooks_record_status() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "inboundowner")
        await drain_background_jobs(session_factory)
        topic = await create_topic(client, owner["auth"])

        bounce = await client.post(
            "/api/v1/email/webhooks/delivery",
            json={
                "email": owner["email"],
                "event_type": "bounce",
                "kind": "notification_replied",
                "provider_message_id": "provider-1",
                "reason": "mailbox unavailable",
            },
        )
        assert bounce.status_code == 200
        assert bounce.json()["data"]["event_type"] == "bounce"

        preferences = await client.get(
            "/api/v1/email/preferences",
            headers={"Authorization": owner["auth"]},
        )
        assert preferences.status_code == 200
        assert preferences.json()["data"]["email_enabled"] is False
        assert preferences.json()["data"]["delivery_status"] == "bounced"

        reenabled = await client.put(
            "/api/v1/email/preferences",
            headers={"Authorization": owner["auth"]},
            json={"email_enabled": True},
        )
        assert reenabled.status_code == 200
        assert reenabled.json()["data"]["delivery_status"] == "ok"

        dropped = await client.post(
            "/api/v1/email/webhooks/delivery",
            json={
                "email": owner["email"],
                "event_type": "dropped",
                "kind": "email_digest",
                "reason": "provider suppressed recipient",
            },
        )
        assert dropped.status_code == 200

        dropped_preferences = await client.get(
            "/api/v1/email/preferences",
            headers={"Authorization": owner["auth"]},
        )
        assert dropped_preferences.status_code == 200
        assert dropped_preferences.json()["data"]["email_enabled"] is False
        assert dropped_preferences.json()["data"]["delivery_status"] == "disabled"

        inbound = await client.post(
            "/api/v1/email/webhooks/inbound-reply",
            json={
                "from_email": owner["email"],
                "topic_id": topic["id"],
                "raw_md": "通过邮件回复的正文。",
                "provider_message_id": "inbound-1",
            },
        )
        assert inbound.status_code == 200
        assert inbound.json()["data"]["status"] == "accepted"
        assert inbound.json()["data"]["topic_id"] == topic["id"]

    await engine.dispose()
