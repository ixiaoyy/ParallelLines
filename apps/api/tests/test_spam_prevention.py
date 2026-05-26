from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import get_settings
from app.core.security import create_token
from app.main import create_app
from app.models.moderation import SpamAction
from app.models.user import User
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "auth": f"Bearer {data['access_token']}",
    }


def access_token_for(user_id: str) -> str:
    return create_token(
        subject=user_id,
        token_type="access",
        settings=get_settings(),
        expires_delta=timedelta(minutes=15),
    )


@pytest.mark.asyncio
async def test_registration_rate_limit_uses_ip_dimension() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for index in range(5):
            response = await client.post(
                "/api/v1/auth/register",
                headers={"x-forwarded-for": "198.51.100.10"},
                json={
                    "username": f"rate{index}",
                    "email": f"rate{index}@example.com",
                    "password": "strong-pass-123",
                },
            )
            assert response.status_code == 201

        limited = await client.post(
            "/api/v1/auth/register",
            headers={"x-forwarded-for": "198.51.100.10"},
            json={
                "username": "rate-over",
                "email": "rate-over@example.com",
                "password": "strong-pass-123",
            },
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"

    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_screened_rules_block_email_and_silence_screened_url() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin = await register_user(client, "spamadmin")
        author = await register_user(client, "screenedauthor")

    async with session_factory() as session:
        admin_user = await session.get(User, admin["id"])
        assert admin_user is not None
        admin_user.role = "admin"
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_headers = {"Authorization": admin["auth"]}
        email_rule = await client.post(
            "/api/v1/moderation/screened-rules",
            headers=admin_headers,
            json={
                "kind": "email",
                "value": "blocked.example",
                "action": "block",
                "note": "测试屏蔽域名。",
            },
        )
        assert email_rule.status_code == 201
        email_rule_id = email_rule.json()["data"]["id"]

        blocked_registration = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "blocked-email",
                "email": "troll@blocked.example",
                "password": "strong-pass-123",
            },
        )
        assert blocked_registration.status_code == 403
        assert blocked_registration.json()["error"]["code"] == "screening_blocked"
        assert "blocked.example" not in blocked_registration.text

        listed_rules = await client.get(
            "/api/v1/moderation/screened-rules?kind=email",
            headers=admin_headers,
        )
        assert listed_rules.status_code == 200
        assert [item["id"] for item in listed_rules.json()["data"]] == [email_rule_id]

        deleted = await client.delete(
            f"/api/v1/moderation/screened-rules/{email_rule_id}",
            headers=admin_headers,
        )
        assert deleted.status_code == 200

        url_rule = await client.post(
            "/api/v1/moderation/screened-rules",
            headers=admin_headers,
            json={"kind": "url", "value": "spam.example", "action": "silence"},
        )
        assert url_rule.status_code == 201

        board = await client.post(
            "/api/v1/boards",
            headers={"Authorization": author["auth"]},
            json={
                "slug": "screened",
                "name": "屏蔽测试",
                "description": "用于测试 URL 屏蔽和自动禁言。",
                "color": "#EF4444",
            },
        )
        assert board.status_code == 201

        blocked_topic = await client.post(
            "/api/v1/boards/screened/topics",
            headers={"Authorization": author["auth"]},
            json={
                "title": "请看这个链接",
                "raw_md": "高风险链接 https://spam.example/deal 不能发布。",
                "tags": ["spam"],
            },
        )
        assert blocked_topic.status_code == 403
        assert blocked_topic.json()["error"]["code"] == "screening_blocked"

        spam_actions = await client.get("/api/v1/moderation/spam-actions", headers=admin_headers)
        assert spam_actions.status_code == 200
        reasons = {item["reason"] for item in spam_actions.json()["data"]}
        assert {"screened_email", "screened_url"}.issubset(reasons)

        audit_logs = await client.get("/api/v1/moderation/audit-logs", headers=admin_headers)
        assert audit_logs.status_code == 200
        audit_actions = {item["action"] for item in audit_logs.json()["data"]}
        assert {"screened_rule_created", "screened_rule_deleted"}.issubset(audit_actions)

    async with session_factory() as session:
        silenced = await session.get(User, author["id"])
        assert silenced is not None
        assert silenced.status == "silenced"
        action_count = len(list(await session.scalars(select(SpamAction))))
        assert action_count >= 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_topic_rate_limits_apply_user_and_ip_dimensions() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "ratelimitowner")
        owner_headers = {"Authorization": owner["auth"]}
        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "rate-board",
                "name": "频控版块",
                "description": "用于测试发帖频控。",
                "color": "#409EFF",
            },
        )
        assert board.status_code == 201

        for index in range(5):
            response = await client.post(
                "/api/v1/boards/rate-board/topics",
                headers={**owner_headers, "x-forwarded-for": "203.0.113.1"},
                json={
                    "title": f"用户维度主题 {index}",
                    "raw_md": "正常内容。",
                    "tags": [],
                },
            )
            assert response.status_code == 201

        user_limited = await client.post(
            "/api/v1/boards/rate-board/topics",
            headers={**owner_headers, "x-forwarded-for": "203.0.113.1"},
            json={"title": "用户维度超限", "raw_md": "正常内容。", "tags": []},
        )
        assert user_limited.status_code == 429
        assert user_limited.json()["error"]["code"] == "rate_limited"

    async with session_factory() as session:
        users = [
            User(
                username=f"ipuser{index}",
                email=f"ipuser{index}@example.com",
                hashed_password="hashed",
                status="active",
            )
            for index in range(11)
        ]
        session.add_all(users)
        await session.commit()
        user_tokens = [(user.id, access_token_for(user.id)) for user in users]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for index, (_user_id, token) in enumerate(user_tokens[:10]):
            response = await client.post(
                "/api/v1/boards/rate-board/topics",
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-forwarded-for": "203.0.113.55",
                },
                json={
                    "title": f"IP 维度主题 {index}",
                    "raw_md": "不同用户同 IP 发帖。",
                    "tags": [],
                },
            )
            assert response.status_code == 201

        _last_user_id, last_token = user_tokens[10]
        ip_limited = await client.post(
            "/api/v1/boards/rate-board/topics",
            headers={
                "Authorization": f"Bearer {last_token}",
                "x-forwarded-for": "203.0.113.55",
            },
            json={"title": "IP 维度超限", "raw_md": "不同用户同 IP 发帖。", "tags": []},
        )
        assert ip_limited.status_code == 429
        assert ip_limited.json()["error"]["code"] == "rate_limited"

    await engine.dispose()
