import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.trust import trust_adjusted_limit
from app.db.base import Base
from app.main import create_app
from app.models.badge import UserTrustLevelEvent
from app.models.user import User
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


def test_trust_rate_limit_boundaries() -> None:
    assert trust_adjusted_limit(5, 0) == 3
    assert trust_adjusted_limit(5, 1) == 5
    assert trust_adjusted_limit(10, 2) == 15
    assert trust_adjusted_limit(10, 3) == 20
    assert trust_adjusted_limit(10, 4) == 20


@pytest.mark.asyncio
async def test_email_verification_grants_badge_and_logs_trust() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        auth = await register_and_verify_user(client, "trustmember")
        assert auth["user"]["role"] == "user"
        assert auth["user"]["trust_level"] == 1
        assert auth["user"]["trust_level_label"] == "基础成员"

        profile = await client.get(
            "/api/v1/users/trustmember",
            headers={"Authorization": f"Bearer {auth['access_token']}"},
        )
        assert profile.status_code == 200
        badges = profile.json()["data"]["badges"]
        assert {badge["badge_slug"] for badge in badges} >= {"verified-member"}

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "trustmember"))
        assert user is not None
        assert user.role == "user"
        assert user.trust_level == 1
        trust_event = await session.scalar(
            select(UserTrustLevelEvent).where(UserTrustLevelEvent.user_id == user.id)
        )
        assert trust_event is not None
        assert trust_event.previous_level == 0
        assert trust_event.next_level == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_can_grant_and_revoke_badge() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_and_verify_user(client, "badgeadmin")
        member = await register_and_verify_user(client, "badgemember")
        admin_auth = {"Authorization": f"Bearer {admin['access_token']}"}

        async with session_factory() as session:
            admin_user = await session.get(User, admin["user"]["id"])
            assert admin_user is not None
            admin_user.role = "admin"
            await session.commit()

        catalog = await client.get("/api/v1/admin/badges", headers=admin_auth)
        assert catalog.status_code == 200
        assert any(badge["slug"] == "first-topic" for badge in catalog.json()["data"])

        granted = await client.post(
            f"/api/v1/admin/users/{member['user']['id']}/badges",
            headers=admin_auth,
            json={"badge_slug": "first-topic", "note": "manual smoke"},
        )
        assert granted.status_code == 200
        granted_badges = granted.json()["data"]["badges"]
        assert any(badge["badge_slug"] == "first-topic" for badge in granted_badges)

        revoked = await client.post(
            f"/api/v1/admin/users/{member['user']['id']}/badges/first-topic/revoke",
            headers=admin_auth,
            json={"reason": "manual revoke"},
        )
        assert revoked.status_code == 200
        remaining_badges = revoked.json()["data"]["badges"]
        assert all(badge["badge_slug"] != "first-topic" for badge in remaining_badges)

    await engine.dispose()
