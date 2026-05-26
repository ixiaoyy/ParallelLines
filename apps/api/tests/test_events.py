from datetime import UTC, datetime, timedelta

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


@pytest.mark.asyncio
async def test_calendar_event_rsvp_deadline_capacity_and_ical() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    start_at = datetime.now(UTC) + timedelta(days=2)
    end_at = start_at + timedelta(hours=2)
    deadline = start_at - timedelta(hours=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        creator = await register_and_verify_user(client, "eventcreator")
        guest = await register_and_verify_user(client, "eventguest")
        creator_headers = {"Authorization": f"Bearer {creator['access_token']}"}
        guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}

        created = await client.post(
            "/api/v1/events",
            headers=creator_headers,
            json={
                "title": "线上社区圆桌",
                "description": "讨论下一阶段路线图。",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "timezone": "Asia/Shanghai",
                "capacity": 1,
                "rsvp_deadline": deadline.isoformat(),
            },
        )
        assert created.status_code == 201
        event_id = created.json()["data"]["id"]

        listed = await client.get("/api/v1/events", headers=creator_headers)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["timezone"] == "Asia/Shanghai"

        rsvp = await client.put(
            f"/api/v1/events/{event_id}/rsvp",
            headers=guest_headers,
            json={"status": "going"},
        )
        assert rsvp.status_code == 200
        assert rsvp.json()["data"]["status"] == "going"

        full = await client.put(
            f"/api/v1/events/{event_id}/rsvp",
            headers=creator_headers,
            json={"status": "going"},
        )
        assert full.status_code == 422
        assert full.json()["error"]["code"] == "event_capacity_full"

        ical = await client.get("/api/v1/events/calendar.ics")
        assert ical.status_code == 200
        assert "BEGIN:VEVENT" in ical.text
        assert "线上社区圆桌" in ical.text

    await engine.dispose()
