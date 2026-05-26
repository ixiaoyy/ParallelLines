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


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "token": data["access_token"],
        "auth": f"Bearer {data['access_token']}",
    }


@pytest.mark.asyncio
async def test_profile_update_privacy_directory_and_activity_permissions() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "profileowner")
        visitor = await register_user(client, "directoryuser")
        owner_headers = {"Authorization": owner["auth"]}
        visitor_headers = {"Authorization": visitor["auth"]}

        invalid_url = await client.patch(
            "/api/v1/users/me/profile",
            headers=owner_headers,
            json={"website_url": "javascript:alert(1)"},
        )
        assert invalid_url.status_code == 422
        assert invalid_url.json()["error"]["code"] == "invalid_profile_url"

        updated = await client.patch(
            "/api/v1/users/me/profile",
            headers=owner_headers,
            json={
                "display_name": "档案主人",
                "bio": "公开简介",
                "website_url": "https://example.com/profileowner",
                "location": "上海 / UTC+8",
                "profile_visibility": "public",
                "show_activity": True,
                "interface_theme": "colorful",
                "locale": "zh-CN",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["bio"] == "公开简介"

        public_profile = await client.get("/api/v1/users/profileowner")
        assert public_profile.status_code == 200
        public_data = public_profile.json()["data"]
        assert "email" not in public_data
        assert public_data["display_name"] == "档案主人"
        assert public_data["website_url"] == "https://example.com/profileowner"

        directory = await client.get("/api/v1/users/directory?sort=contribution")
        assert directory.status_code == 200
        assert all("email" not in row for row in directory.json()["data"])
        assert {row["username"] for row in directory.json()["data"]}.issuperset(
            {"profileowner", "directoryuser"}
        )

        private_update = await client.patch(
            "/api/v1/users/me/profile",
            headers=owner_headers,
            json={"profile_visibility": "private", "show_activity": False},
        )
        assert private_update.status_code == 200

        private_as_visitor = await client.get(
            "/api/v1/users/profileowner",
            headers=visitor_headers,
        )
        assert private_as_visitor.status_code == 200
        assert private_as_visitor.json()["data"]["bio"] is None
        assert private_as_visitor.json()["data"]["show_activity"] is False

        private_as_owner = await client.get("/api/v1/users/profileowner", headers=owner_headers)
        assert private_as_owner.status_code == 200
        assert private_as_owner.json()["data"]["bio"] == "公开简介"
        assert private_as_owner.json()["data"]["can_edit"] is True

        hidden_activity = await client.get(
            "/api/v1/users/profileowner/activity",
            headers=visitor_headers,
        )
        assert hidden_activity.status_code == 403
        assert hidden_activity.json()["error"]["code"] == "profile_activity_private"

    await engine.dispose()
