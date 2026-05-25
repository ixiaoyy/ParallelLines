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


@pytest.mark.asyncio
async def test_admin_migration_import_preview_run_export_and_errors() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_and_verify_user(client, "migrationadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        headers = {"Authorization": f"Bearer {admin['access_token']}"}

        payload = {
            "source": "discourse-json",
            "users": [
                {"username": "imported_author", "email": "imported_author@example.com"},
                {"username": "reply_author", "email": "reply_author@example.com"},
            ],
            "boards": [{"slug": "imported", "name": "导入版块", "description": "历史内容"}],
            "topics": [
                {
                    "external_id": "topic-1",
                    "board_slug": "imported",
                    "author_username": "imported_author",
                    "title": "迁移来的主题",
                    "slug": "imported-topic",
                    "tags": ["Migration"],
                    "raw_md": "第一帖内容",
                }
            ],
            "posts": [
                {
                    "topic_external_id": "topic-1",
                    "topic_slug": "imported-topic",
                    "board_slug": "imported",
                    "author_username": "reply_author",
                    "post_number": 2,
                    "raw_md": "回复内容",
                }
            ],
        }

        preview = await client.post(
            "/api/v1/admin/migrations/import/preview",
            headers=headers,
            json=payload,
        )
        assert preview.status_code == 200
        assert preview.json()["data"]["dry_run"] is True
        assert preview.json()["data"]["created"] == 5

        empty_export = await client.get("/api/v1/admin/migrations/export", headers=headers)
        assert empty_export.status_code == 200
        assert all(board["slug"] != "imported" for board in empty_export.json()["data"]["boards"])

        run = await client.post(
            "/api/v1/admin/migrations/import/run", headers=headers, json=payload
        )
        assert run.status_code == 200
        assert run.json()["data"]["created"] == 5

        second_run = await client.post(
            "/api/v1/admin/migrations/import/run",
            headers=headers,
            json=payload,
        )
        assert second_run.status_code == 200
        assert second_run.json()["data"]["skipped"] >= 4

        exported = await client.get("/api/v1/admin/migrations/export", headers=headers)
        assert exported.status_code == 200
        data = exported.json()["data"]
        assert any(board["slug"] == "imported" for board in data["boards"])
        assert any(topic["slug"] == "imported-topic" for topic in data["topics"])
        assert not any("hashed_password" in user for user in data["users"])

        bad = await client.post(
            "/api/v1/admin/migrations/import/preview",
            headers=headers,
            json={
                "source": "bad-json",
                "topics": [
                    {
                        "board_slug": "missing",
                        "author_username": "imported_author",
                        "title": "缺失版块",
                    }
                ],
            },
        )
        assert bad.status_code == 200
        assert bad.json()["data"]["errors"] == 1

    await engine.dispose()
