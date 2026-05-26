import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.moderation import AuditLog
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
async def test_plugin_config_ui_extensions_and_hook_isolation() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "pluginuser")
        admin = await register_and_verify_user(client, "pluginadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        user_headers = {"Authorization": f"Bearer {user['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        denied = await client.get("/api/v1/admin/plugins", headers=user_headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "admin_required"

        plugins = await client.get("/api/v1/admin/plugins", headers=admin_headers)
        assert plugins.status_code == 200
        registry = {plugin["id"]: plugin for plugin in plugins.json()["data"]}
        assert registry["example-topic-tools"]["enabled"] is False
        assert registry["example-topic-tools"]["ui_extensions"][0]["slot"] == "app.nav"

        extensions = await client.get("/api/v1/site/extensions")
        assert extensions.status_code == 200
        assert extensions.json()["data"] == []

        enabled = await client.put(
            "/api/v1/admin/plugins/example-topic-tools",
            headers=admin_headers,
            json={"enabled": True},
        )
        assert enabled.status_code == 200
        assert enabled.json()["data"]["enabled"] is True

        extensions = await client.get("/api/v1/site/extensions")
        assert extensions.status_code == 200
        extension_data = extensions.json()["data"]
        assert len(extension_data) == 1
        assert extension_data[0]["plugin_id"] == "example-topic-tools"
        assert extension_data[0]["slot"] == "app.nav"

        board = await client.post(
            "/api/v1/boards",
            headers=user_headers,
            json={
                "slug": "plugins",
                "name": "插件讨论",
                "description": "讨论扩展点、事件 hook 与 UI 插槽。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        topic = await client.post(
            "/api/v1/boards/plugins/topics",
            headers=user_headers,
            json={"title": "插件事件能被记录吗", "raw_md": "用主题创建事件验证插件 hook。"},
        )
        assert topic.status_code == 201

        broken_enabled = await client.put(
            "/api/v1/admin/plugins/broken-example",
            headers=admin_headers,
            json={"enabled": True},
        )
        assert broken_enabled.status_code == 200

        isolated_topic = await client.post(
            "/api/v1/boards/plugins/topics",
            headers=user_headers,
            json={"title": "异常插件不能影响发帖", "raw_md": "核心主题创建必须继续成功。"},
        )
        assert isolated_topic.status_code == 201

        disabled = await client.put(
            "/api/v1/admin/plugins/example-topic-tools",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert disabled.status_code == 200

        extensions = await client.get("/api/v1/site/extensions")
        assert extensions.status_code == 200
        assert extensions.json()["data"] == []

    async with session_factory() as session:
        actions = await session.scalars(select(AuditLog.action).order_by(AuditLog.created_at))
        audit_actions = list(actions)
        assert "plugin_example_topic_created" in audit_actions
        assert "plugin_hook_failed" in audit_actions

    await engine.dispose()
