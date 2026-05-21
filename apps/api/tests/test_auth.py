import time
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.core.config import get_settings
from app.core.security import create_token
from app.db.base import Base
from app.main import create_app
from app.models.user import User, UserSecurityToken
from app.services.auth import TOTP_STEP_SECONDS, hotp
from app.services.email import clear_email_outbox, latest_email_secret, latest_verification_code
from tests.helpers import drain_background_jobs, register_and_verify_user


@asynccontextmanager
async def auth_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    clear_email_outbox()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_factory

    await engine.dispose()


@pytest.mark.anyio
async def test_register_login_and_me() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    clear_email_outbox()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={"username": "大脚板", "email": "lina@example.com", "password": "strong-pass-123"},
        )
        assert register.status_code == 201
        register_data = register.json()["data"]
        assert register_data["verification_required"] is True
        assert register_data["email"] == "lina@example.com"
        assert register_data["dev_verification_code"]

        blocked_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "大脚板", "password": "strong-pass-123"},
        )
        assert blocked_login.status_code == 401
        assert blocked_login.json()["error"]["code"] == "email_not_verified"

        bad_verify = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": "lina@example.com", "code": "000000"},
        )
        assert bad_verify.status_code == 422
        assert bad_verify.json()["error"]["code"] == "invalid_verification_code"

        verify = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": "lina@example.com", "code": register_data["dev_verification_code"]},
        )
        assert verify.status_code == 200
        verify_data = verify.json()["data"]
        access_token = verify_data["access_token"]
        assert verify_data["user"]["role"] == "user"
        assert verify_data["user"]["level"] == 0

        login = await client.post(
            "/api/v1/auth/login",
            json={"account": "大脚板", "password": "strong-pass-123"},
        )
        assert login.status_code == 200

        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me.status_code == 200
        assert me.json()["data"]["username"] == "大脚板"
        assert me.json()["data"]["level"] == 0

        invalid_username = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "bad name",
                "email": "bad-name@example.com",
                "password": "strong-pass-123",
            },
        )
        assert invalid_username.status_code == 422
        assert invalid_username.json()["error"]["code"] == "validation_error"

    await engine.dispose()


@pytest.mark.anyio
async def test_resend_verification_rate_limit() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    clear_email_outbox()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "resend",
                "email": "resend@example.com",
                "password": "strong-pass-123",
            },
        )
        assert register.status_code == 201

        limited = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "resend@example.com"},
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "verification_resend_limited"

        await drain_background_jobs(session_factory)
        assert latest_verification_code("resend@example.com")

    await engine.dispose()


@pytest.mark.anyio
async def test_me_rejects_pending_verification_user() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    pending_user_id = ""
    async with session_factory() as session:
        user = User(
            username="pending",
            email="pending@example.com",
            hashed_password="hashed",
            status="pending_verification",
        )
        session.add(user)
        await session.flush()
        pending_user_id = user.id
        await session.commit()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        access_token = create_token(
            subject=pending_user_id,
            token_type="access",
            settings=get_settings(),
            expires_delta=timedelta(minutes=15),
        )
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me.status_code == 401
        assert me.json()["error"]["code"] == "invalid_token"

    await engine.dispose()


@pytest.mark.anyio
async def test_password_reset_is_uniform_expiring_and_one_time() -> None:
    async with auth_client() as (client, session_factory):
        token_pair = await register_and_verify_user(
            client,
            "resetter",
            email="resetter@example.com",
            password="old-pass-123",
        )
        old_access_token = token_pair["access_token"]

        known = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "resetter@example.com"},
        )
        unknown = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "missing-reset@example.com"},
        )
        assert known.status_code == 200
        assert unknown.status_code == 200
        assert known.json()["data"] == unknown.json()["data"]
        await drain_background_jobs(session_factory)
        assert latest_email_secret("missing-reset@example.com", kind="password_reset") is None

        expired_token = latest_email_secret("resetter@example.com", kind="password_reset")
        assert expired_token
        async with session_factory() as session:
            reset_row = await session.scalar(
                select(UserSecurityToken)
                .where(
                    UserSecurityToken.email == "resetter@example.com",
                    UserSecurityToken.purpose == "password_reset",
                )
                .order_by(UserSecurityToken.sent_at.desc())
            )
            assert reset_row
            reset_row.expires_at = reset_row.sent_at - timedelta(minutes=1)
            await session.commit()

        expired = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": expired_token, "new_password": "new-pass-123"},
        )
        assert expired.status_code == 422
        assert expired.json()["error"]["code"] == "invalid_reset_token"

        await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "resetter@example.com"},
        )
        await drain_background_jobs(session_factory)
        fresh_token = latest_email_secret("resetter@example.com", kind="password_reset")
        assert fresh_token and fresh_token != expired_token

        confirmed = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": fresh_token, "new_password": "new-pass-123"},
        )
        assert confirmed.status_code == 200

        reused = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": fresh_token, "new_password": "newer-pass-123"},
        )
        assert reused.status_code == 422
        assert reused.json()["error"]["code"] == "invalid_reset_token"

        revoked_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {old_access_token}"},
        )
        assert revoked_me.status_code == 401
        assert revoked_me.json()["error"]["code"] == "invalid_token"

        old_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "resetter", "password": "old-pass-123"},
        )
        assert old_login.status_code == 401

        new_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "resetter@example.com", "password": "new-pass-123"},
        )
        assert new_login.status_code == 200
        assert new_login.json()["data"]["access_token"]


@pytest.mark.anyio
async def test_email_change_token_updates_email_and_cannot_be_reused() -> None:
    async with auth_client() as (client, session_factory):
        token_pair = await register_and_verify_user(
            client,
            "mailchanger",
            email="mailchanger@example.com",
            password="strong-pass-123",
        )
        headers = {"Authorization": f"Bearer {token_pair['access_token']}"}

        requested = await client.post(
            "/api/v1/auth/email-change/request",
            headers=headers,
            json={"new_email": "new-mailchanger@example.com", "password": "strong-pass-123"},
        )
        assert requested.status_code == 200
        assert requested.json()["data"]["email"] == "new-mailchanger@example.com"

        await drain_background_jobs(session_factory)
        token = latest_email_secret("new-mailchanger@example.com", kind="email_change")
        assert token
        confirmed = await client.post(
            "/api/v1/auth/email-change/confirm",
            json={"token": token},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["data"]["email"] == "new-mailchanger@example.com"

        reused = await client.post(
            "/api/v1/auth/email-change/confirm",
            json={"token": token},
        )
        assert reused.status_code == 422
        assert reused.json()["error"]["code"] == "invalid_email_change_token"

        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["data"]["email"] == "new-mailchanger@example.com"


@pytest.mark.anyio
async def test_user_can_list_and_revoke_active_sessions() -> None:
    async with auth_client() as (client, _session_factory):
        first_pair = await register_and_verify_user(
            client,
            "sessioned",
            email="sessioned@example.com",
            password="strong-pass-123",
        )
        first_headers = {"Authorization": f"Bearer {first_pair['access_token']}"}

        second_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "sessioned", "password": "strong-pass-123"},
        )
        assert second_login.status_code == 200
        second_pair = second_login.json()["data"]
        second_headers = {"Authorization": f"Bearer {second_pair['access_token']}"}

        listed = await client.get("/api/v1/auth/sessions", headers=second_headers)
        assert listed.status_code == 200
        sessions = listed.json()["data"]
        assert {item["id"] for item in sessions} == {
            first_pair["session_id"],
            second_pair["session_id"],
        }
        assert [item["id"] for item in sessions if item["current"]] == [second_pair["session_id"]]

        revoked = await client.delete(
            f"/api/v1/auth/sessions/{first_pair['session_id']}",
            headers=second_headers,
        )
        assert revoked.status_code == 200

        rejected = await client.get("/api/v1/auth/me", headers=first_headers)
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "invalid_token"

        after_revoke = await client.get("/api/v1/auth/sessions", headers=second_headers)
        assert after_revoke.status_code == 200
        assert [item["id"] for item in after_revoke.json()["data"]] == [second_pair["session_id"]]

        third_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "sessioned", "password": "strong-pass-123"},
        )
        assert third_login.status_code == 200
        third_pair = third_login.json()["data"]
        third_headers = {"Authorization": f"Bearer {third_pair['access_token']}"}

        revoked_others = await client.post(
            "/api/v1/auth/sessions/revoke-others",
            headers=third_headers,
        )
        assert revoked_others.status_code == 200
        assert revoked_others.json()["data"]["revoked"] == 1

        rejected_second = await client.get("/api/v1/auth/me", headers=second_headers)
        assert rejected_second.status_code == 401
        current_me = await client.get("/api/v1/auth/me", headers=third_headers)
        assert current_me.status_code == 200


@pytest.mark.anyio
async def test_two_factor_login_requires_second_factor_and_recovery_code_is_one_time() -> None:
    async with auth_client() as (client, _session_factory):
        token_pair = await register_and_verify_user(
            client,
            "totpuser",
            email="totpuser@example.com",
            password="strong-pass-123",
        )
        headers = {"Authorization": f"Bearer {token_pair['access_token']}"}

        setup = await client.post(
            "/api/v1/auth/2fa/setup",
            headers=headers,
            json={"password": "strong-pass-123"},
        )
        assert setup.status_code == 200
        secret = setup.json()["data"]["secret"]
        code = hotp(secret, int(time.time()) // TOTP_STEP_SECONDS)

        enabled = await client.post(
            "/api/v1/auth/2fa/enable",
            headers=headers,
            json={"secret": secret, "code": code},
        )
        assert enabled.status_code == 200
        recovery_codes = enabled.json()["data"]["recovery_codes"]
        assert len(recovery_codes) == 10

        login = await client.post(
            "/api/v1/auth/login",
            json={"account": "totpuser", "password": "strong-pass-123"},
        )
        assert login.status_code == 200
        login_data = login.json()["data"]
        assert login_data["two_factor_required"] is True
        assert login_data["access_token"] is None
        assert login_data["challenge_token"]

        bad_code = await client.post(
            "/api/v1/auth/2fa/verify-login",
            json={"challenge_token": login_data["challenge_token"], "code": "000000"},
        )
        assert bad_code.status_code == 401
        assert bad_code.json()["error"]["code"] == "invalid_two_factor_code"

        verified = await client.post(
            "/api/v1/auth/2fa/verify-login",
            json={
                "challenge_token": login_data["challenge_token"],
                "code": hotp(secret, int(time.time()) // TOTP_STEP_SECONDS),
            },
        )
        assert verified.status_code == 200
        assert verified.json()["data"]["access_token"]

        recovery_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "totpuser", "password": "strong-pass-123"},
        )
        recovery_challenge = recovery_login.json()["data"]["challenge_token"]
        recovery_verified = await client.post(
            "/api/v1/auth/2fa/verify-login",
            json={"challenge_token": recovery_challenge, "code": recovery_codes[0]},
        )
        assert recovery_verified.status_code == 200

        reuse_login = await client.post(
            "/api/v1/auth/login",
            json={"account": "totpuser", "password": "strong-pass-123"},
        )
        reused_recovery = await client.post(
            "/api/v1/auth/2fa/verify-login",
            json={
                "challenge_token": reuse_login.json()["data"]["challenge_token"],
                "code": recovery_codes[0],
            },
        )
        assert reused_recovery.status_code == 401
        assert reused_recovery.json()["error"]["code"] == "invalid_two_factor_code"
