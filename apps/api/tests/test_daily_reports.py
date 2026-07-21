from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.daily_report import DailyReportInput
from app.services.daily_report_provider import parse_provider_result
from app.services.daily_reports import build_local_report, require_report_structure, text_similarity
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


def test_daily_report_local_rendering_and_similarity() -> None:
    payload = DailyReportInput(
        work_date=date(2026, 7, 21),
        recurring_work=["处理用户反馈", "检查线上服务状态"],
        extra_work=["排查登录异常"],
        risks=[],
        tomorrow_plan=["继续跟进灰度反馈"],
        style="detailed",
    )

    report = build_local_report(payload)

    assert "## 今日完成" in report
    assert "## 问题风险" not in report
    assert "## 明日计划" in report
    assert "处理用户反馈" in report
    assert text_similarity(report, report) == 1.0
    assert text_similarity(report, "完全不相关的内容") < 0.1
    require_report_structure(report, include_risks=False)


def test_daily_report_provider_response_parsing() -> None:
    result = parse_provider_result(
        {
            "model": "test-model",
            "choices": [
                {
                    "message": {
                        "content": (
                            '```json\n{"reply":"已调整","report":"## 今日完成\\n- 完成检查",'
                            '"preference_suggestion":"避免使用推进"}\n```'
                        )
                    }
                }
            ],
        },
        "fallback-model",
    )

    assert result.model_name == "test-model"
    assert result.provider_mode == "ai"
    assert result.preference_suggestion == "避免使用推进"


@pytest.mark.asyncio
async def test_daily_report_account_isolation_prompt_and_history() -> None:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as connection:
        await reset_test_database(connection)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        daily_report_ai_provider="local",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_and_verify_user(client, "dailyowner")
        stranger = await register_and_verify_user(client, "dailystranger")
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}

        profile_response = await client.get(
            "/api/v1/daily-reports/profile",
            headers=owner_headers,
        )
        assert profile_response.status_code == 200
        profile = profile_response.json()["data"]
        assert profile["ai_enabled"] is False
        assert profile["prompt_version"] == 1

        started_response = await client.post(
            "/api/v1/daily-reports/sessions",
            headers=owner_headers,
            json={
                "work_date": "2026-07-21",
                "recurring_work": ["处理用户反馈", "检查线上服务状态"],
                "extra_work": ["排查登录异常"],
                "risks": [],
                "tomorrow_plan": ["继续跟进灰度反馈"],
                "style": "detailed",
            },
        )
        assert started_response.status_code == 201
        started = started_response.json()["data"]
        assert started["provider_mode"] == "local_fallback"
        assert "## 问题风险" not in started["current_draft"]

        forbidden_response = await client.get(
            f"/api/v1/daily-reports/sessions/{started['id']}",
            headers=stranger_headers,
        )
        assert forbidden_response.status_code == 404

        followup_response = await client.post(
            f"/api/v1/daily-reports/sessions/{started['id']}/messages",
            headers=owner_headers,
            json={
                "message": "以后每次都避免使用推进",
                "current_content": started["current_draft"],
                "expected_version": 1,
            },
        )
        assert followup_response.status_code == 200
        followup = followup_response.json()["data"]
        assert followup["version"] == 2
        suggestion = followup["messages"][-1]["preference_suggestion"]
        assert suggestion == "以后每次都避免使用推进"

        preference_response = await client.post(
            "/api/v1/daily-reports/profile/preferences",
            headers=owner_headers,
            json={"requirement": suggestion, "expected_version": 1},
        )
        assert preference_response.status_code == 200
        updated_profile = preference_response.json()["data"]
        assert updated_profile["prompt_version"] == 2
        assert suggestion in updated_profile["custom_prompt"]
        assert suggestion in updated_profile["preferences"]["requirements"]

        confirm_response = await client.post(
            f"/api/v1/daily-reports/sessions/{started['id']}/confirm",
            headers=owner_headers,
            json={"content": followup["current_draft"], "expected_version": 2},
        )
        assert confirm_response.status_code == 200
        report_id = confirm_response.json()["data"]["id"]

        history_response = await client.get("/api/v1/daily-reports", headers=owner_headers)
        assert history_response.status_code == 200
        assert [item["id"] for item in history_response.json()["data"]] == [report_id]

        stranger_history = await client.get(
            "/api/v1/daily-reports",
            headers=stranger_headers,
        )
        assert stranger_history.status_code == 200
        assert stranger_history.json()["data"] == []

        delete_response = await client.delete(
            f"/api/v1/daily-reports/{report_id}",
            headers=owner_headers,
        )
        assert delete_response.status_code == 200
        deleted_session = await client.get(
            f"/api/v1/daily-reports/sessions/{started['id']}",
            headers=owner_headers,
        )
        assert deleted_session.status_code == 404

        clear_response = await client.delete(
            "/api/v1/daily-reports/history",
            headers=owner_headers,
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["data"] is True

    await engine.dispose()
