import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.user import User
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


def github_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_github_external_integration_health_webhook_and_unfurl() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_and_verify_user(client, "externaladmin")
        await promote_admin(session_factory, admin["user"]["id"])
        headers = {"Authorization": f"Bearer {admin['access_token']}"}

        health = await client.get("/api/v1/admin/external-integrations", headers=headers)
        assert health.status_code == 200
        github = next(item for item in health.json()["data"] if item["provider"] == "github")
        assert github["status"] == "disabled"

        missing = await client.put(
            "/api/v1/admin/external-integrations/github",
            headers=headers,
            json={"enabled": True, "config": {}},
        )
        assert missing.status_code == 200
        assert missing.json()["data"]["status"] == "misconfigured"
        assert "missing_config:webhook_secret" in missing.json()["data"]["issues"]

        configured = await client.put(
            "/api/v1/admin/external-integrations/github",
            headers=headers,
            json={
                "enabled": True,
                "config": {
                    "webhook_secret": "github-secret",
                    "repository_url": "https://github.com/acme/app",
                },
            },
        )
        assert configured.status_code == 200
        assert configured.json()["data"]["status"] == "healthy"
        assert configured.json()["data"]["config"]["webhook_secret"] == "********"

        payload = {
            "action": "opened",
            "repository": {"full_name": "acme/app"},
            "issue": {
                "number": 42,
                "title": "OAuth callback fails",
                "state": "open",
                "html_url": "https://github.com/acme/app/issues/42",
            },
        }
        body = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
        invalid = await client.post(
            "/api/v1/integrations/github/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Delivery": "delivery-1",
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": "sha256=bad",
            },
        )
        assert invalid.status_code == 403
        assert invalid.json()["error"]["code"] == "external_webhook_signature_invalid"

        received = await client.post(
            "/api/v1/integrations/github/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Delivery": "delivery-1",
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": github_signature("github-secret", body),
            },
        )
        assert received.status_code == 200
        assert received.json()["data"]["status"] == "processed"

        unfurled = await client.get(
            "/api/v1/integrations/github/issue",
            params={"url": "https://github.com/acme/app/issues/42"},
        )
        assert unfurled.status_code == 200
        assert unfurled.json()["data"]["title"] == "OAuth callback fails"
        assert unfurled.json()["data"]["source"] == "webhook_cache"

        events = await client.get("/api/v1/admin/external-integrations/events", headers=headers)
        assert events.status_code == 200
        assert events.json()["data"][0]["retry_count"] == 0

    await engine.dispose()
