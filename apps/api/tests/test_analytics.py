from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.moderation import AuditLog
from app.models.user import User
from app.services.site_visits import is_probable_bot_user_agent
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


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        ("Mozilla/5.0 (compatible; Googlebot/2.1)", True),
        ("curl/8.10.1", True),
        ("Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36", False),
        (None, False),
    ],
)
def test_site_visit_bot_user_agent_detection(user_agent: str | None, expected: bool) -> None:
    assert is_probable_bot_user_agent(user_agent) is expected


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
        persona = await register_and_verify_user(client, "analyticspersona")
        await promote_admin(session_factory, admin["user"]["id"])
        async with session_factory() as session:
            regular_user = await session.get(User, user["user"]["id"])
            persona_user = await session.get(User, persona["user"]["id"])
            assert regular_user is not None
            assert persona_user is not None
            assert regular_user.is_persona is False
            persona_user.is_persona = True
            await session.commit()
        user_headers = {"Authorization": f"Bearer {user['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
        persona_headers = {"Authorization": f"Bearer {persona['access_token']}"}

        denied = await client.get("/api/v1/admin/analytics", headers=user_headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "admin_required"
        denied_reports = await client.get("/api/v1/admin/analytics/reports", headers=user_headers)
        assert denied_reports.status_code == 403
        assert denied_reports.json()["error"]["code"] == "admin_required"
        denied_report = await client.get(
            "/api/v1/admin/analytics/reports/daily_activity",
            headers=user_headers,
        )
        assert denied_report.status_code == 403
        assert denied_report.json()["error"]["code"] == "admin_required"
        denied_export = await client.get(
            "/api/v1/admin/analytics/reports/daily_activity/export.csv",
            headers=user_headers,
        )
        assert denied_export.status_code == 403
        assert denied_export.json()["error"]["code"] == "admin_required"

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

        campaign_visit = await client.post(
            "/api/v1/site/visits",
            headers={"X-ParallelLines-Visitor": "visitor-alpha"},
            json={
                "path": "/?utm_source=zhihu&utm_medium=social&utm_campaign=launch",
                "title": "平行线",
                "referrer": "https://www.zhihu.com/question/1",
            },
        )
        assert campaign_visit.status_code == 202
        assert campaign_visit.json()["data"]["recorded"] is True

        search_visit = await client.post(
            "/api/v1/site/visits",
            headers=admin_headers,
            json={
                "path": "/b/analytics",
                "title": "运营分析",
                "referrer": "https://www.google.com/search?q=parallel+lines",
            },
        )
        assert search_visit.status_code == 202
        assert search_visit.json()["data"]["recorded"] is True

        member_visit = await client.post(
            "/api/v1/site/visits",
            headers=user_headers,
            json={"path": "/b/analytics", "title": "运营分析", "referrer": None},
        )
        assert member_visit.status_code == 202
        assert member_visit.json()["data"]["recorded"] is True

        persona_visit = await client.post(
            "/api/v1/site/visits",
            headers=persona_headers,
            json={"path": "/", "title": "平行线", "referrer": None},
        )
        assert persona_visit.status_code == 202
        assert persona_visit.json()["data"]["recorded"] is True

        bot_visit = await client.post(
            "/api/v1/site/visits",
            headers={
                "X-ParallelLines-Visitor": "visitor-googlebot",
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)",
            },
            json={"path": "/", "title": "平行线", "referrer": None},
        )
        assert bot_visit.status_code == 202
        assert bot_visit.json()["data"]["recorded"] is False

        overview = await client.get(
            "/api/v1/admin/analytics",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert overview.status_code == 200
        overview_data = overview.json()["data"]
        assert overview_data["totals"]["registrations"] == 2
        assert overview_data["series"][0]["registrations"] == 2
        assert overview_data["totals"]["topics"] >= 1
        assert overview_data["totals"]["likes"] >= 1
        assert overview_data["totals"]["flags"] >= 1
        assert overview_data["totals"]["page_views"] >= 2
        assert overview_data["totals"]["unique_visitors"] >= 2
        assert overview_data["totals"]["authenticated_member_visitors"] == 1
        assert overview_data["totals"]["anonymous_visitors"] == 1
        assert overview_data["totals"]["operator_visitors"] == 2
        assert overview_data["totals"]["external_referrals"] >= 2
        assert overview_data["top_boards"][0]["slug"] == "analytics"
        assert {source["source_type"] for source in overview_data["traffic_sources"]} >= {
            "campaign",
            "search",
        }
        assert any(
            page["path"].startswith("/?utm_source=zhihu") for page in overview_data["entry_pages"]
        )

        reports = await client.get("/api/v1/admin/analytics/reports", headers=admin_headers)
        assert reports.status_code == 200
        report_ids = [report["id"] for report in reports.json()["data"]]
        assert "daily_activity" in report_ids
        assert "traffic_sources" in report_ids
        assert "entry_pages" in report_ids

        report = await client.get(
            "/api/v1/admin/analytics/reports/daily_activity",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert report.status_code == 200
        assert report.json()["data"]["rows"][0]["topics"] >= 1
        assert report.json()["data"]["rows"][0]["page_views"] >= 2
        assert report.json()["data"]["rows"][0]["registrations"] == 2

        source_report = await client.get(
            "/api/v1/admin/analytics/reports/traffic_sources",
            headers=admin_headers,
            params={"start_date": today, "end_date": today},
        )
        assert source_report.status_code == 200
        assert source_report.json()["data"]["rows"][0]["visit_count"] >= 1

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
