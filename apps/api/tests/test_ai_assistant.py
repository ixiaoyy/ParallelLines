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


async def set_role(
    session_factory: async_sessionmaker[AsyncSession], user_id: str, role: str
) -> None:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.role = role
        await session.commit()


@pytest.mark.asyncio
async def test_ai_summary_similar_topics_and_moderation_advice() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_and_verify_user(client, "aiowner")
        moderator = await register_and_verify_user(client, "aimod")
        await set_role(session_factory, moderator["user"]["id"], "moderator")
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        moderator_headers = {"Authorization": f"Bearer {moderator['access_token']}"}

        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "ai-help",
                "name": "AI 协作",
                "description": "AI 摘要和推荐测试版块。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201
        topic = await client.post(
            "/api/v1/boards/ai-help/topics",
            headers=owner_headers,
            json={
                "title": "后台任务 webhook 重试失败如何排查",
                "raw_md": "webhook 投递失败后需要查看 retrying 状态和 dead letter 日志。",
                "tags": ["webhook", "worker"],
            },
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        summary = await client.post(
            f"/api/v1/topics/{topic_id}/ai-summary/refresh",
            headers=owner_headers,
        )
        assert summary.status_code == 200
        assert "webhook" in summary.json()["data"]["summary"].lower()
        assert summary.json()["data"]["cost_units"] >= 1

        similar = await client.post(
            "/api/v1/ai/similar-topics",
            json={
                "title": "Webhook retrying 队列为什么失败",
                "raw_md": "想排查 worker dead letter 和 webhook 重试。",
                "tags": ["webhook"],
            },
        )
        assert similar.status_code == 200
        assert similar.json()["data"][0]["id"] == topic_id

        advice = await client.post(
            "/api/v1/ai/moderation-advice",
            headers=moderator_headers,
            json={"target_type": "post", "raw_text": "这里疑似泄露 token 和密码，请处理。"},
        )
        assert advice.status_code == 200
        assert advice.json()["data"]["risk_level"] == "high"
        assert advice.json()["data"]["auto_action_allowed"] is False

    await engine.dispose()
