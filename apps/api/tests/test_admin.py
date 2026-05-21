import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.user import User
from app.services.email import clear_email_outbox
from tests.helpers import drain_background_jobs, register_and_verify_user


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


async def promote_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


@pytest.mark.asyncio
async def test_admin_settings_public_settings_and_registration_gate() -> None:
    clear_email_outbox()
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_user(client, "adminops")
        member = await register_user(client, "plainmember")
        await promote_admin(session_factory, admin["id"])

        forbidden = await client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": member["auth"]},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "admin_required"

        settings = await client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": admin["auth"]},
        )
        assert settings.status_code == 200
        setting_keys = {item["key"] for item in settings.json()["data"]}
        assert {"site_title", "registration_enabled", "upload_max_bytes"}.issubset(setting_keys)

        title = await client.put(
            "/api/v1/admin/settings/site_title",
            headers={"Authorization": admin["auth"]},
            json={"value": "平行线实验场"},
        )
        assert title.status_code == 200
        assert title.json()["data"]["value"] == "平行线实验场"

        public_settings = await client.get("/api/v1/site/settings")
        assert public_settings.status_code == 200
        assert public_settings.json()["data"]["settings"]["site_title"] == "平行线实验场"

        disabled = await client.put(
            "/api/v1/admin/settings/registration_enabled",
            headers={"Authorization": admin["auth"]},
            json={"value": False},
        )
        assert disabled.status_code == 200

        blocked_register = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "lateuser",
                "email": "lateuser@example.com",
                "password": "strong-pass-123",
            },
        )
        assert blocked_register.status_code == 403
        assert blocked_register.json()["error"]["code"] == "registration_disabled"

        audit_logs = await client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": admin["auth"]},
        )
        assert audit_logs.status_code == 200
        actions = {item["action"] for item in audit_logs.json()["data"]}
        assert "site_setting_updated" in actions

    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_user_management_system_panel_and_mail_logs() -> None:
    clear_email_outbox()
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_user(client, "systemadmin")
        member = await register_user(client, "manageduser")
        await drain_background_jobs(session_factory)
        await promote_admin(session_factory, admin["id"])
        admin_headers = {"Authorization": admin["auth"]}

        users = await client.get("/api/v1/admin/users?query=managed", headers=admin_headers)
        assert users.status_code == 200
        user_rows = users.json()["data"]
        assert [row["id"] for row in user_rows] == [member["id"]]

        updated = await client.put(
            f"/api/v1/admin/users/{member['id']}",
            headers=admin_headers,
            json={"role": "moderator", "status": "silenced", "level": 2},
        )
        assert updated.status_code == 200
        updated_user = updated.json()["data"]
        assert updated_user["role"] == "moderator"
        assert updated_user["status"] == "silenced"
        assert updated_user["level"] == 2

        system = await client.get("/api/v1/admin/system", headers=admin_headers)
        assert system.status_code == 200
        system_data = system.json()["data"]
        assert system_data["stats"]["users"] >= 2
        assert "database" in {service["name"] for service in system_data["services"]}
        assert system_data["recent_email_logs"]
        assert "@" in system_data["recent_email_logs"][0]["to_email"]

        audit_logs = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
        assert audit_logs.status_code == 200
        actions = {item["action"] for item in audit_logs.json()["data"]}
        assert "user_admin_updated" in actions

    await engine.dispose()
