import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.asyncio
async def test_push_subscription_lifecycle() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "pushuser")
        headers = {"Authorization": f"Bearer {user['access_token']}"}

        initial = await client.get("/api/v1/notifications/push-subscription", headers=headers)
        assert initial.status_code == 200
        assert initial.json()["data"]["subscription"] is None

        saved = await client.post(
            "/api/v1/notifications/push-subscription",
            headers=headers,
            json={
                "endpoint": "https://push.example/subscriptions/abc123456789",
                "keys": {"p256dh": "p256dh-key-material", "auth": "auth-key"},
                "user_agent": "pytest",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["data"]["subscription"]["enabled"] is True

        deleted = await client.delete("/api/v1/notifications/push-subscription", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["data"]["subscription"] is None

    await engine.dispose()
