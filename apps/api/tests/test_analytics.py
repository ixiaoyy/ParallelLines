from datetime import date

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
async def test_admin_analytics_overview_reports_and_csv_export() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    today = date.today().isoformat()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "analyticsuser")
        admin = await register_and_verify_user(client, "analyticsadmin")
        await promote_admin(session_factory, admin["user"]["id"])
        user_headers = {"Authorization": f"Bearer {user['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}

        denied = await client.get("/api/v1/admin/analytics", headers=user_headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "admin_required"

        board = await client.post(
            "/api/v1/boards",
            headers=user_headers,
            json={
                "slug": "analytics",
                "name": "运营分析",
                "description": "用于验证运营报表的公开版块。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        topic = await client.post(
            "/api/v1/boards/analytics/topics",
            headers=user_headers,
            json={"title": "本周活跃趋势怎么看", "raw_md": "需要统计注册、主题、回复和点赞。"},
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        like = await client.put(f"/api/v1/topics/{topic_id}/like", headers=admin_headers)
        assert like.status_code == 200

        flag = await client.post(
            "/api/v1/moderation/flags",
            headers=admin_headers,
            json={"target_type": "topic", "target_id": topic_id, "reason": "spam"},
        )
        assert flag.status_code == 201

        overview = await client.get(
            "/api/v1/admin/analytics",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert overview.status_code == 200
        overview_data = overview.json()["data"]
        assert overview_data["totals"]["registrations"] >= 2
        assert overview_data["totals"]["topics"] >= 1
        assert overview_data["totals"]["likes"] >= 1
        assert overview_data["totals"]["flags"] >= 1
        assert overview_data["top_boards"][0]["slug"] == "analytics"

        reports = await client.get("/api/v1/admin/analytics/reports", headers=admin_headers)
        assert reports.status_code == 200
        assert "daily_activity" in [report["id"] for report in reports.json()["data"]]

        report = await client.get(
            "/api/v1/admin/analytics/reports/daily_activity",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert report.status_code == 200
        assert report.json()["data"]["rows"][0]["topics"] >= 1

        export = await client.get(
            "/api/v1/admin/analytics/reports/daily_activity/export.csv",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert export.status_code == 200
        assert "text/csv" in export.headers["content-type"]
        assert "registrations" in export.text

    async with session_factory() as session:
        action = await session.scalar(
            select(AuditLog.action).where(AuditLog.action == "analytics_csv_exported")
        )
        assert action == "analytics_csv_exported"

    await engine.dispose()
