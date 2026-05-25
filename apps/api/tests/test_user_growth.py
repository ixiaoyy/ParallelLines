import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.growth import experience_to_next_level, level_for_experience
from app.db.base import Base
from app.main import create_app
from app.models.user import User, UserPointEvent
from tests.helpers import register_and_verify_user


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
        "points": data["user"]["points_balance"],
        "experience": data["user"]["experience_total"],
    }


def test_level_rules_cover_boundaries() -> None:
    assert level_for_experience(49) == 0
    assert experience_to_next_level(49) == 1
    assert level_for_experience(50) == 1
    assert level_for_experience(151) == 2
    assert experience_to_next_level(6_000) == 0


@pytest.mark.asyncio
async def test_growth_awards_and_like_idempotency() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "growthowner")
        member = await register_user(client, "growthmember")
        assert owner["points"] == 20
        assert owner["experience"] == 20

        board = await client.post(
            "/api/v1/boards",
            headers={"Authorization": owner["auth"]},
            json={
                "slug": "growth",
                "name": "成长体系",
                "description": "积分经验成长测试版块。",
                "color": "#10B981",
            },
        )
        assert board.status_code == 201

        topic = await client.post(
            "/api/v1/boards/growth/topics",
            headers={"Authorization": owner["auth"]},
            json={
                "title": "发主题应该增加经验积分",
                "raw_md": "这个主题用于验证成长流水。",
                "tags": ["growth"],
            },
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        posts = await client.get(f"/api/v1/topics/{topic_id}/posts")
        assert posts.status_code == 200
        first_post_id = posts.json()["data"][0]["id"]

        reply = await client.post(
            f"/api/v1/topics/{topic_id}/posts",
            headers={"Authorization": member["auth"]},
            json={"raw_md": "回复也会获得成长奖励。"},
        )
        assert reply.status_code == 201

        like = await client.put(
            f"/api/v1/posts/{first_post_id}/like",
            headers={"Authorization": member["auth"]},
        )
        repeat_like = await client.put(
            f"/api/v1/posts/{first_post_id}/like",
            headers={"Authorization": member["auth"]},
        )
        assert like.status_code == 200
        assert repeat_like.status_code == 200

    async with session_factory() as session:
        owner_row = await session.get(User, owner["id"])
        member_row = await session.get(User, member["id"])
        assert owner_row is not None
        assert member_row is not None
        assert owner_row.points_balance == 26
        assert owner_row.experience_total == 39
        assert owner_row.level == level_for_experience(39)
        assert member_row.points_balance == 22
        assert member_row.experience_total == 28

        like_events = await session.scalar(
            select(func.count(UserPointEvent.id)).where(
                UserPointEvent.user_id == owner["id"],
                UserPointEvent.source_type == "content_liked",
            )
        )
        assert like_events == 1

    await engine.dispose()
