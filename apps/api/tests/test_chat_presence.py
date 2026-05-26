import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.services.chat_realtime import ChatRealtimeBus, ChatRealtimeEvent
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


def parse_sse_payload(text: str, event_name: str) -> dict[str, object]:
    for frame in text.strip().split("\n\n"):
        lines = frame.splitlines()
        event = next(
            (line.removeprefix("event:").strip() for line in lines if line.startswith("event:")),
            "",
        )
        if event != event_name:
            continue
        data = "\n".join(
            line.removeprefix("data:").strip() for line in lines if line.startswith("data:")
        )
        return json.loads(data)
    raise AssertionError(f"SSE event {event_name} not found")


@pytest.mark.asyncio
async def test_private_board_chat_acl_presence_and_reconnect_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "chat_realtime_backend", "memory")
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_and_verify_user(client, "chatowner")
        outsider = await register_and_verify_user(client, "chatstranger")
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        outsider_headers = {"Authorization": f"Bearer {outsider['access_token']}"}

        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "ops-room",
                "name": "运维密室",
                "description": "只允许成员进入的实时排障频道。",
                "color": "#0EA5E9",
                "visibility": "private",
            },
        )
        assert board.status_code == 201

        channel = await client.post(
            "/api/v1/chat/channels",
            headers=owner_headers,
            json={
                "name": "排障现场",
                "channel_type": "board",
                "board_slug": "ops-room",
            },
        )
        assert channel.status_code == 201
        channel_id = channel.json()["data"]["id"]

        outsider_channels = await client.get("/api/v1/chat/channels", headers=outsider_headers)
        assert outsider_channels.status_code == 200
        assert channel_id not in [item["id"] for item in outsider_channels.json()["data"]]

        denied = await client.get(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=outsider_headers,
        )
        assert denied.status_code == 404
        assert denied.json()["error"]["code"] == "chat_channel_not_found"

        first = await client.post(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=owner_headers,
            json={"raw_text": "数据库连接池告警，先看慢查询。"},
        )
        assert first.status_code == 201
        first_message_id = first.json()["data"]["id"]

        second = await client.post(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=owner_headers,
            json={"raw_text": "重连后应能补到这一条消息。"},
        )
        assert second.status_code == 201

        stream = await client.get(
            f"/api/v1/chat/channels/{channel_id}/stream",
            headers=owner_headers,
            params={"after_id": first_message_id, "once": True},
        )
        assert stream.status_code == 200
        payload = parse_sse_payload(stream.text, "chat")
        messages = payload["messages"]
        assert isinstance(messages, list)
        assert [message["raw_text"] for message in messages] == ["重连后应能补到这一条消息。"]

        presence = await client.put(
            f"/api/v1/chat/channels/{channel_id}/presence",
            headers=owner_headers,
            json={"status": "online", "typing": True},
        )
        assert presence.status_code == 200
        assert presence.json()["data"]["typing"] is True

        presence_list = await client.get(
            f"/api/v1/chat/channels/{channel_id}/presence",
            headers=owner_headers,
        )
        assert presence_list.status_code == 200
        assert presence_list.json()["data"][0]["user"]["username"] == "chatowner"

        search = await client.get(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=owner_headers,
            params={"q": "重连"},
        )
        assert search.status_code == 200
        assert search.json()["data"]["messages"][0]["id"] == second.json()["data"]["id"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_message_rate_limit_blocks_bursts(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "chat_realtime_backend", "memory")
    monkeypatch.setattr(settings, "rate_limit_chat_message_user", 1)
    monkeypatch.setattr(settings, "rate_limit_chat_message_ip", 100)
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user = await register_and_verify_user(client, "chatburst")
        headers = {
            "Authorization": f"Bearer {user['access_token']}",
            "x-forwarded-for": "198.51.100.77",
        }
        channel = await client.post(
            "/api/v1/chat/channels",
            headers=headers,
            json={"name": "突发消息测试", "channel_type": "public", "slug": "chat-burst"},
        )
        assert channel.status_code == 201
        channel_id = channel.json()["data"]["id"]

        first = await client.post(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=headers,
            json={"raw_text": "第一条消息允许发送。"},
        )
        assert first.status_code == 201

        limited = await client.post(
            f"/api/v1/chat/channels/{channel_id}/messages",
            headers=headers,
            json={"raw_text": "第二条突发消息应该被频控。"},
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"

    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_realtime_bus_fans_out_memory_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "chat_realtime_backend", "memory")
    bus = ChatRealtimeBus(settings)
    listener = bus.listen("42")
    pending = asyncio.create_task(anext(listener))

    try:
        await asyncio.sleep(0)
        await bus.publish(
            ChatRealtimeEvent(
                channel_id="42",
                event_type="message",
                payload_json='{"messages":[],"presence":[]}',
                last_message_id="100",
            )
        )
        event = await asyncio.wait_for(pending, timeout=1)
        assert event.channel_id == "42"
        assert event.event_type == "message"
        assert event.last_message_id == "100"
        assert '"messages"' in event.payload_json
    finally:
        await listener.aclose()
