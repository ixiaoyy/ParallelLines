import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.user import User
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def promote_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


@pytest.mark.asyncio
async def test_topic_localization_update_lookup_and_fallback() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_and_verify_user(client, "localowner")
        admin = await register_and_verify_user(client, "localadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "localization",
                "name": "本地化版块",
                "description": "讨论多语言内容",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201
        topic = await client.post(
            "/api/v1/boards/localization/topics",
            headers=owner_headers,
            json={"title": "中文主题标题", "raw_md": "中文正文", "tags": ["i18n"]},
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        update = await client.put(
            f"/api/v1/topics/{topic_id}/localizations/en-US",
            headers=admin_headers,
            json={"title": "English topic title"},
        )
        assert update.status_code == 200
        assert update.json()["data"]["title"] == "English topic title"
        assert update.json()["data"]["fallback_used"] is False

        localized = await client.get(f"/api/v1/topics/{topic_id}/localizations/en_US")
        assert localized.status_code == 200
        assert localized.json()["data"]["locale"] == "en-US"
        assert localized.json()["data"]["title"] == "English topic title"

        fallback = await client.get(f"/api/v1/topics/{topic_id}/localizations/fr-FR")
        assert fallback.status_code == 200
        assert fallback.json()["data"]["title"] == "中文主题标题"
        assert fallback.json()["data"]["fallback_used"] is True

        topic_after = await client.get(f"/api/v1/topics/{topic_id}")
        assert topic_after.status_code == 200
        assert topic_after.json()["data"]["title_localizations"] == {"en-US": "English topic title"}

        remove = await client.put(
            f"/api/v1/topics/{topic_id}/localizations/en-US",
            headers=admin_headers,
            json={"title": None},
        )
        assert remove.status_code == 200
        assert remove.json()["data"]["fallback_used"] is True

    await engine.dispose()
