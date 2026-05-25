import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.background_job import BackgroundJob
from app.models.integration import WebhookDelivery
from app.models.user import User
from app.services import integrations as integrations_module
from app.services.integrations import IntegrationService, webhook_signature
from app.workers.background_jobs import run_once
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def promote_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


@pytest.mark.asyncio
async def test_api_key_scope_gate_and_admin_disable_controls() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_and_verify_user(client, "integrationadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        no_scope = await client.post(
            "/api/v1/admin/api-keys",
            headers=admin_headers,
            json={"name": "No scope", "scopes": []},
        )
        assert no_scope.status_code == 201
        no_scope_token = no_scope.json()["data"]["token"]

        denied = await client.get(
            "/api/v1/integrations/me",
            headers={"X-API-Key": no_scope_token},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "api_key_scope_required"

        read_key = await client.post(
            "/api/v1/admin/api-keys",
            headers=admin_headers,
            json={"name": "Read key", "scopes": ["read"]},
        )
        assert read_key.status_code == 201
        read_data = read_key.json()["data"]
        read_token = read_data["token"]

        allowed = await client.get(
            "/api/v1/integrations/me",
            headers={"Authorization": f"Bearer {read_token}"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["data"]["scopes"] == ["read"]

        disabled_key = await client.post(
            f"/api/v1/admin/api-keys/{read_data['api_key']['id']}/disable",
            headers=admin_headers,
        )
        assert disabled_key.status_code == 200
        assert disabled_key.json()["data"]["disabled_at"] is not None

        disabled_access = await client.get(
            "/api/v1/integrations/me",
            headers={"X-API-Key": read_token},
        )
        assert disabled_access.status_code == 401
        assert disabled_access.json()["error"]["code"] == "api_key_invalid"

        webhook = await client.post(
            "/api/v1/admin/webhooks",
            headers=admin_headers,
            json={
                "name": "Topic relay",
                "url": "https://receiver.example/webhook",
                "events": ["topic.created"],
            },
        )
        assert webhook.status_code == 201
        webhook_data = webhook.json()["data"]

        disabled_webhook = await client.post(
            f"/api/v1/admin/webhooks/{webhook_data['webhook']['id']}/disable",
            headers=admin_headers,
        )
        assert disabled_webhook.status_code == 200
        assert disabled_webhook.json()["data"]["active"] is False

    await engine.dispose()


@pytest.mark.asyncio
async def test_webhook_signature_retry_and_delivery_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    captured: dict[str, object] = {}

    def failing_post_json(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> integrations_module.WebhookHttpResult:
        captured.update(
            {
                "url": url,
                "body": body,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        raise RuntimeError("receiver failed")

    monkeypatch.setattr(integrations_module, "_post_json", failing_post_json)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_and_verify_user(client, "webhookadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        webhook = await client.post(
            "/api/v1/admin/webhooks",
            headers=admin_headers,
            json={
                "name": "Retry receiver",
                "url": "https://receiver.example/retry",
                "events": ["topic.created"],
            },
        )
        assert webhook.status_code == 201
        secret = webhook.json()["data"]["secret"]

    async with session_factory() as session:
        deliveries = await IntegrationService(session).enqueue_event(
            "topic.created",
            {"topic_id": "topic-1", "title": "Webhook smoke"},
            commit=True,
        )
        assert len(deliveries) == 1

    processed = await run_once(
        session_factory=session_factory,
        queues=("webhooks",),
        enqueue_scheduled=False,
    )
    assert processed == 1

    headers = captured["headers"]
    assert isinstance(headers, dict)
    body = captured["body"]
    assert isinstance(body, bytes)
    timestamp = headers["X-ParallelLines-Timestamp"]
    assert headers["X-ParallelLines-Signature"] == webhook_signature(secret, body, timestamp)

    async with session_factory() as session:
        delivery = await session.scalar(select(WebhookDelivery))
        assert delivery is not None
        assert delivery.status == "retrying"
        assert delivery.attempt_count == 1
        assert delivery.last_error == "receiver failed"
        assert delivery.next_attempt_at is not None

        retry_job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.task_name == "deliver_webhook",
                BackgroundJob.status == "queued",
            )
        )
        assert retry_job is not None
        assert retry_job.payload == {"delivery_id": delivery.id}

    await engine.dispose()
