import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app


@pytest.mark.anyio
async def test_register_login_and_me() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={"username": "lina", "email": "lina@example.com", "password": "strong-pass-123"},
        )
        assert register.status_code == 201
        access_token = register.json()["data"]["access_token"]

        login = await client.post(
            "/api/v1/auth/login",
            json={"account": "lina@example.com", "password": "strong-pass-123"},
        )
        assert login.status_code == 200

        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me.status_code == 200
        assert me.json()["data"]["username"] == "lina"

    await engine.dispose()
