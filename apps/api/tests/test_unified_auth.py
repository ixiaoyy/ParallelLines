"""真实 ORM 的独立内存 SQLite / ASGI 回归；不读取运行数据库、不访问外网。"""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from itertools import count
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.v1 import auth, auth_chat_sso, auth_unified
from app.api.v1.dependencies import get_current_user
from app.core.chat_sso import CLIENT_ID, VerifiedLogin
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, AuthenticationError, PermissionDeniedError
from app.core.security import create_token, decode_token
from app.db.base import utcnow
from app.db.session import get_session
from app.models.user import EmailVerificationCode, User, UserSecurityToken, UserSession
from app.schemas.auth import RefreshRequest
from app.schemas.unified_auth import UnifiedAuthorizeRequest
from app.services.auth import AuthService
from app.services.chat_sso import ChatSsoService
from app.services.unified_auth import BROWSER_PURPOSE, COOKIE_NAME, UnifiedAuthService

MAIN = "https://pingxingxian.space"
CIRCLE = "https://forum.pingxingxian.space"
CALLBACK = CIRCLE + "/auth/unified/callback"
PREFIX = "/api/v1/auth/unified"
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


class MemoryAsyncSession:
    """仅适配实际服务使用的 ORM 接口；所有写入只发生在本测试的内存引擎。"""

    def __init__(self, session):
        self.sync = session
        self.ids = count(1000)

    def add(self, row):
        if isinstance(row, (UserSecurityToken, UserSession)) and row.id is None:
            row.id = str(next(self.ids))
        self.sync.add(row)

    async def get(self, *args, **kwargs):
        return self.sync.get(*args, **kwargs)

    async def scalar(self, statement):
        return self.sync.scalar(statement)

    async def scalars(self, statement):
        return self.sync.scalars(statement)

    async def execute(self, statement):
        return self.sync.execute(statement)

    async def commit(self):
        self.sync.commit()

    async def flush(self):
        self.sync.flush()

    async def refresh(self, row):
        self.sync.refresh(row)


@pytest.fixture
def memory():
    settings = Settings(
        _env_file=None,
        unified_auth_enabled=True,
        public_site_url=MAIN,
        public_forum_url=CIRCLE,
        jwt_secret_key="isolated-unified-auth-fixture-key-not-a-real-secret",
        chat_sso_enabled=True,
        chat_sso_bridge_secret="isolated-bridge-fixture-secret-at-least-32",
        chat_sso_finish_url=MAIN + "/auth/oidc/interaction/finish",
        chat_sso_login_policy="active_main",
    )
    engine = create_engine("sqlite:///:memory:")
    for model in (User, UserSession, UserSecurityToken, EmailVerificationCode):
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as db:
        for uid in ("1", "2"):
            db.add(
                User(
                    id=uid,
                    username="member-" + uid,
                    email="member-" + uid + "@example.com",
                    hashed_password="non-login-fixture",
                    status="active",
                    role="user",
                )
            )
        for sid, uid in (("10", "1"), ("11", "1"), ("20", "2"), ("21", "2")):
            db.add(
                UserSession(
                    id=sid,
                    user_id=uid,
                    refresh_token_hash="non-secret-fixture",
                    last_seen_at=utcnow(),
                    created_at=utcnow() - timedelta(minutes=10),
                )
            )
        db.commit()
        yield db, MemoryAsyncSession(db), settings
    engine.dispose()


@pytest.fixture
def app(memory):
    db, adapter, settings = memory
    app = FastAPI()

    @app.exception_handler(AppError)
    async def typed_failure(_request, error):
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {"code": error.code, "message": error.message, "details": error.details},
            },
        )

    app.include_router(auth_unified.router, prefix="/api/v1")
    app.include_router(auth_chat_sso.router, prefix="/api/v1")

    async def isolated_session():
        try:
            yield adapter
        finally:
            db.rollback()

    app.dependency_overrides[get_session] = isolated_session
    app.dependency_overrides[get_settings] = lambda: settings
    return app


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=MAIN) as client:
        yield client


def bearer(settings, user_id="1", session_id="10", *, seconds=3600, typ="access"):
    return create_token(
        subject=user_id,
        session_id=session_id,
        token_type=typ,
        settings=settings,
        expires_delta=timedelta(seconds=seconds),
    )


async def bootstrap(client, settings, *, user_id="1", session_id="10", replace=False):
    return await client.post(
        PREFIX + "/bootstrap",
        json={"replace": replace},
        headers={
            "Origin": MAIN,
            "Authorization": "Bearer " + bearer(settings, user_id, session_id),
        },
    )


async def authorization_code(client):
    response = await client.post(
        PREFIX + "/authorize",
        json={
            "client_id": "parallellines-circle",
            "redirect_uri": CALLBACK,
            "state": "isolated-state",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
        headers={"Origin": MAIN},
    )
    assert response.status_code == 200, response.text
    query = parse_qs(urlsplit(response.json()["data"]["redirect_url"]).query)
    assert query["state"] == ["isolated-state"]
    return query["code"][0]


async def exchange(
    client, code, *, verifier=VERIFIER, origin=CIRCLE, redirect=CALLBACK, host=CIRCLE
):
    return await client.post(
        host + PREFIX + "/exchange",
        json={
            "client_id": "parallellines-circle",
            "redirect_uri": redirect,
            "code": code,
            "code_verifier": verifier,
        },
        headers={"Origin": origin},
    )


@pytest.mark.asyncio
async def test_bootstrap_cookie_and_short_access_share_sid_without_refresh(client, memory):
    db, adapter, settings = memory
    response = await bootstrap(client, settings)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["authenticated"] is True and data["subject"] == data["user"]["id"] == "1"
    assert data["session_id"] == "10" and 0 < data["expires_in"] <= 300
    assert "refresh_token" not in data
    claims = decode_token(data["access_token"], settings=settings)
    assert claims["sub"] == "1" and claims["sid"] == "10"
    cookie = response.headers["set-cookie"]
    assert COOKIE_NAME in cookie and "HttpOnly" in cookie and "Secure" in cookie
    assert "SameSite=lax" in cookie and "Path=/" in cookie and "Domain=" not in cookie
    raw_cookie = client.cookies.get(COOKIE_NAME)
    assert raw_cookie.count(".") == 1
    handle, generation = raw_cookie.split(".")
    pointer = db.scalar(
        select(UserSecurityToken).where(UserSecurityToken.purpose == BROWSER_PURPOSE)
    )
    assert pointer.token_hash == UnifiedAuthService(adapter, settings)._hash(
        BROWSER_PURPOSE, handle
    )
    assert handle not in pointer.payload and generation in pointer.payload
    with pytest.raises(AuthenticationError):
        decode_token(raw_cookie, settings=settings, expected_type="access")
    with pytest.raises(AuthenticationError):
        await get_current_user(raw_cookie, adapter, settings)
    state = await client.get(PREFIX + "/state")
    assert state.json()["data"] == {
        "authenticated": True,
        "subject": "1",
        "auth_epoch": data["auth_epoch"],
    }
    assert state.headers["cache-control"] == "no-store"
    assert state.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_cookie_authority_ignores_expired_local_bearer(client, memory):
    settings = memory[2]
    first = await bootstrap(client, settings)
    response = await client.post(
        PREFIX + "/bootstrap",
        json={},
        headers={
            "Origin": MAIN,
            "Authorization": "Bearer stale-local-storage-not-a-valid-jwt",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["auth_epoch"] == first.json()["data"]["auth_epoch"]


@pytest.mark.asyncio
async def test_failed_explicit_replacement_does_not_revoke_existing_sid_or_cookie(client, memory):
    db, _, settings = memory
    await bootstrap(client, settings)
    old_cookie = client.cookies.get(COOKIE_NAME)
    response = await client.post(
        PREFIX + "/bootstrap",
        json={"replace": True},
        headers={
            "Origin": MAIN,
            "Authorization": "Bearer invalid-new-login",
        },
    )
    assert response.status_code == 401
    assert db.get(UserSession, "10").revoked_at is None
    assert client.cookies.get(COOKIE_NAME) == old_cookie
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_pkce_exchange_is_single_use_and_does_not_copy_refresh_token(client, memory):
    settings = memory[2]
    first = await bootstrap(client, settings)
    code = await authorization_code(client)
    response = await exchange(client, code)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["session_id"] == "10" and data["subject"] == data["user"]["id"] == "1"
    assert data["auth_epoch"] == first.json()["data"]["auth_epoch"]
    assert "refresh_token" not in data
    assert decode_token(data["access_token"], settings=settings)["sid"] == "10"
    replay = await exchange(client, code)
    assert replay.status_code == 400 and replay.json()["error"]["code"] == "invalid_unified_code"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["verifier", "redirect", "origin", "host"])
async def test_pkce_rejects_mismatched_request_without_consuming_valid_code(client, memory, kind):
    await bootstrap(client, memory[2])
    code = await authorization_code(client)
    kwargs = {
        "verifier": {"verifier": "x" * 64},
        "redirect": {"redirect": CALLBACK + "/other"},
        "origin": {"origin": "https://attacker.invalid"},
        "host": {"host": MAIN},
    }[kind]
    denied = await exchange(client, code, **kwargs)
    assert denied.status_code in (400, 403)
    assert (await exchange(client, code)).status_code == 200


@pytest.mark.asyncio
async def test_revoked_or_expired_authorization_cannot_be_exchanged(client, memory):
    db, _, settings = memory
    await bootstrap(client, settings)
    code = await authorization_code(client)
    row = db.scalar(
        select(UserSecurityToken).where(UserSecurityToken.purpose == "unified_auth_code")
    )
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert (await exchange(client, code)).status_code == 400
    code = await authorization_code(client)
    db.get(UserSession, "10").revoked_at = utcnow()
    db.commit()
    assert (await exchange(client, code)).status_code == 401


@pytest.mark.asyncio
async def test_switch_revokes_only_previous_browser_sid_and_old_chat_binding(client, memory):
    db, adapter, settings = memory
    await bootstrap(client, settings)
    bridge = ChatSsoService(adapter, settings)
    approval = await bridge.approve_verified(
        VerifiedLogin("1", "10", int((utcnow() + timedelta(hours=1)).timestamp()), True),
        "isolated-interaction",
    )
    binding = await bridge.exchange(CLIENT_ID, "isolated-interaction", approval["approval_code"])
    old_access = bearer(settings)
    second = await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    assert second.status_code == 200
    assert second.json()["data"]["subject"] == "2"
    assert db.get(UserSession, "10").revoked_at is not None
    assert all(db.get(UserSession, sid).revoked_at is None for sid in ("11", "20", "21"))
    assert (await bridge.session_state(CLIENT_ID, binding["binding_id"]))["active"] is False
    with pytest.raises(AuthenticationError):
        await get_current_user(old_access, adapter, settings)


@pytest.mark.asyncio
async def test_cookie_only_logout_is_real_sid_revoke_without_other_device_logout(client, memory):
    db, _, settings = memory
    await bootstrap(client, settings)
    response = await client.post(PREFIX + "/logout", json={}, headers={"Origin": MAIN})
    assert response.status_code == 200 and response.json()["data"]["authenticated"] is False
    assert db.get(UserSession, "10").revoked_at is not None
    assert db.get(UserSession, "11").revoked_at is None
    assert client.cookies.get(COOKIE_NAME) is None
    assert (await client.get(PREFIX + "/state")).json()["data"]["authenticated"] is False


@pytest.mark.asyncio
async def test_stale_rp_logout_ticket_cannot_clear_replacement_identity(client, memory):
    db, _, settings = memory
    await bootstrap(client, settings)
    ticket_response = await client.post(
        CIRCLE + PREFIX + "/logout-ticket",
        json={
            "return_uri": CIRCLE + "/",
        },
        headers={"Origin": CIRCLE, "Authorization": "Bearer " + bearer(settings)},
    )
    assert ticket_response.status_code == 200
    url = ticket_response.json()["data"]["logout_url"]
    ticket = parse_qs(urlsplit(url).query)["ticket"][0]
    await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    replacement_cookie = client.cookies.get(COOKIE_NAME)
    response = await client.post(
        PREFIX + "/logout", json={"ticket": ticket}, headers={"Origin": MAIN}
    )
    assert response.status_code == 200
    assert response.json()["data"]["subject"] == "2"
    assert response.json()["data"]["return_url"] == CIRCLE + "/"
    assert client.cookies.get(COOKIE_NAME) == replacement_cookie
    assert db.get(UserSession, "20").revoked_at is None
    assert (
        await client.post(
            PREFIX + "/logout",
            json={"ticket": ticket},
            headers={
                "Origin": MAIN,
            },
        )
    ).status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", [None, "null", "https://attacker.invalid", CIRCLE])
async def test_cookie_mutations_require_exact_main_origin(client, memory, origin):
    await bootstrap(client, memory[2])
    for path, body in (
        ("/bootstrap", {}),
        ("/logout", {}),
        (
            "/authorize",
            {
                "client_id": "parallellines-circle",
                "redirect_uri": CALLBACK,
                "state": "isolated-state",
                "code_challenge": CHALLENGE,
                "code_challenge_method": "S256",
            },
        ),
    ):
        response = await client.post(
            PREFIX + path, json=body, headers={"Origin": origin} if origin else {}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_main_cookie_endpoints_reject_circle_host_and_sidless_bootstrap(client, memory):
    settings = memory[2]
    response = await client.post(
        PREFIX + "/bootstrap",
        json={},
        headers={
            "Origin": MAIN,
            "Authorization": "Bearer " + bearer(settings, session_id=None),
        },
    )
    assert response.status_code == 401 and "set-cookie" not in response.headers
    assert (await client.get(CIRCLE + PREFIX + "/state")).status_code == 403
    assert (
        await client.post(
            CIRCLE + PREFIX + "/bootstrap",
            json={},
            headers={
                "Origin": MAIN,
                "Authorization": "Bearer " + bearer(settings),
            },
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_schema_errors_never_echo_ticket_or_verifier(client):
    secret = "invalid verifier fixture never echo"
    response = await client.post(
        CIRCLE + PREFIX + "/exchange",
        json={
            "client_id": "parallellines-circle",
            "redirect_uri": CALLBACK,
            "code": "z" * 43,
            "code_verifier": secret,
        },
        headers={"Origin": CIRCLE},
    )
    assert response.status_code == 400
    assert secret not in response.text and "z" * 43 not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_chat_cookie_approval_has_trusted_new_marker_and_retains_old_bearer_path(
    client, memory
):
    _, adapter, settings = memory
    await bootstrap(client, settings)
    response = await client.post(
        PREFIX + "/chat-approve",
        json={
            "interaction_id": "unified-interaction",
        },
        headers={"Origin": MAIN},
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    bridge = ChatSsoService(adapter, settings)
    current = await bridge.exchange(CLIENT_ID, "unified-interaction", result["approval_code"])
    assert current["unified_browser"] is True
    state = await bridge.session_state(CLIENT_ID, current["binding_id"])
    assert state["unified_browser"] is True and state["sub"] == "1"
    old_approval = await bridge.approve(
        bearer(settings), memory[0].get(User, "1"), "old-interaction"
    )
    old = await bridge.exchange(CLIENT_ID, "old-interaction", old_approval["approval_code"])
    assert old.get("unified_browser", False) is False


@pytest.mark.asyncio
async def test_bridge_logout_ticket_requires_original_bridge_secret_and_bound_sid(client, memory):
    _, adapter, settings = memory
    bridge = ChatSsoService(adapter, settings)
    approval = await bridge.approve_verified(
        VerifiedLogin("1", "10", int((utcnow() + timedelta(hours=1)).timestamp()), True),
        "bridge-interaction",
    )
    binding = await bridge.exchange(CLIENT_ID, "bridge-interaction", approval["approval_code"])
    body = {"client_id": CLIENT_ID, "binding_id": binding["binding_id"], "return_uri": MAIN + "/"}
    path = "/api/v1/auth/chat-sso/unified-logout-ticket"
    denied = await client.post(path, json=body)
    assert denied.status_code == 401
    response = await client.post(
        path,
        json=body,
        headers={
            "Authorization": "Bearer " + settings.chat_sso_bridge_secret,
        },
    )
    assert response.status_code == 200
    ticket = parse_qs(urlsplit(response.json()["data"]["logout_url"]).query)["ticket"][0]
    logout = await client.post(
        PREFIX + "/logout", json={"ticket": ticket}, headers={"Origin": MAIN}
    )
    assert logout.status_code == 200
    assert (await bridge.session_state(CLIENT_ID, binding["binding_id"]))["active"] is False


@pytest.mark.asyncio
async def test_disabled_feature_and_chat_policy_remain_fail_closed(client, memory):
    _, _, settings = memory
    await bootstrap(client, settings)
    settings.chat_sso_login_policy = "disabled"
    response = await client.post(
        PREFIX + "/chat-approve",
        json={
            "interaction_id": "denied-interaction",
        },
        headers={"Origin": MAIN},
    )
    assert response.status_code == 401
    settings.unified_auth_enabled = False
    assert (await client.get(PREFIX + "/state")).status_code == 403


@pytest.mark.asyncio
async def test_existing_token_pair_and_refresh_shapes_unchanged(memory):
    db, adapter, settings = memory
    auth = AuthService(adapter, settings)
    pair = await auth._token_pair(db.get(User, "1"))
    assert set(pair.model_dump()) == {
        "access_token",
        "refresh_token",
        "token_type",
        "user",
        "session_id",
    }
    refreshed = await auth.refresh(RefreshRequest(refresh_token=pair.refresh_token))
    assert set(refreshed) == {"access_token", "token_type"}
    assert decode_token(refreshed["access_token"], settings=settings)["sid"] == pair.session_id


def test_http_requires_explicit_loopback_and_uses_distinct_non_host_cookie(memory):
    _, adapter, settings = memory
    settings.public_site_url = "http://localhost:5173"
    settings.public_forum_url = "http://localhost:5174"
    with pytest.raises(PermissionDeniedError):
        UnifiedAuthService(adapter, settings)
    settings.unified_auth_allow_loopback_http = True
    service = UnifiedAuthService(adapter, settings)
    assert service.cookie_name == "pl-unified-local" and service.cookie_secure is False
    settings.public_site_url = "http://main.attacker.invalid"
    with pytest.raises(PermissionDeniedError):
        UnifiedAuthService(adapter, settings)


def test_fixed_circle_schema_rejects_extra_role_and_arbitrary_callback_fields():
    with pytest.raises(ValueError):
        UnifiedAuthorizeRequest(
            client_id="parallellines-circle",
            redirect_uri=CALLBACK,
            state="isolated-state",
            code_challenge=CHALLENGE,
            code_challenge_method="S256",
            role="admin",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "https://attacker.invalid/",
        CIRCLE + "/?next=attacker",
        "https://fable.pingxingxian.space/",
    ],
)
async def test_logout_return_allowlist_does_not_expand_to_external_products(client, memory, target):
    response = await client.post(
        PREFIX + "/logout-ticket",
        json={"return_uri": target},
        headers={
            "Origin": MAIN,
            "Authorization": "Bearer " + bearer(memory[2]),
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_unified_redirect"
    assert memory[0].scalar(select(UserSecurityToken)) is None


@pytest.mark.asyncio
async def test_state_has_no_credentials_and_does_not_treat_access_jwt_as_central_cookie(
    client, memory
):
    client.cookies.set(COOKIE_NAME, bearer(memory[2]), domain="pingxingxian.space", path="/")
    response = await client.get(PREFIX + "/state")
    assert response.status_code == 200
    assert response.json()["data"] == {"authenticated": False, "subject": None, "auth_epoch": None}


@pytest.mark.asyncio
async def test_database_failure_is_not_anonymous_authority(client, memory, monkeypatch):
    _, adapter, settings = memory
    await bootstrap(client, settings)

    async def unavailable(*_args, **_kwargs):
        raise OSError("isolated unavailable authority")

    monkeypatch.setattr(adapter, "get", unavailable)
    with pytest.raises(OSError, match="isolated unavailable authority"):
        await client.get(PREFIX + "/state")


@pytest.mark.asyncio
async def test_short_cookie_expiry_is_not_extended_by_the_server_session_limit(client, memory):
    from starlette.requests import Request

    db, adapter, settings = memory
    await bootstrap(client, settings)
    pointer = db.scalar(
        select(UserSecurityToken).where(UserSecurityToken.purpose == BROWSER_PURPOSE)
    )
    pointer.expires_at = utcnow() + timedelta(seconds=60)
    db.commit()
    raw = client.cookies.get(COOKIE_NAME)
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "server": ("pingxingxian.space", 443),
            "headers": [(b"cookie", (COOKIE_NAME + "=" + raw).encode())],
        }
    )
    login = await UnifiedAuthService(adapter, settings).cookie_login(request)
    assert login is not None
    assert 0 < (login.expires_at - utcnow()).total_seconds() <= 60


@pytest.mark.asyncio
async def test_unified_marker_is_server_owned_and_malformed_persisted_markers_fail_closed(
    client, memory
):
    import json

    from app.core.chat_sso import token_hash

    db, adapter, settings = memory
    await bootstrap(client, settings)
    injected = await client.post(
        PREFIX + "/chat-approve",
        json={
            "interaction_id": "unified-interaction",
            "unified_browser": True,
        },
        headers={"Origin": MAIN},
    )
    assert injected.status_code == 400
    bridge = ChatSsoService(adapter, settings)
    approved = await bridge.approve_verified(
        VerifiedLogin("1", "10", int((utcnow() + timedelta(hours=1)).timestamp()), True),
        "unified-interaction",
    )
    current = await bridge.exchange(CLIENT_ID, "unified-interaction", approved["approval_code"])
    record = db.scalar(
        select(UserSecurityToken).where(
            UserSecurityToken.token_hash == token_hash(current["binding_id"]),
        )
    )
    payload = json.loads(record.payload)
    payload["unified_browser"] = "true"
    record.payload = json.dumps(payload)
    db.commit()
    assert (await bridge.session_state(CLIENT_ID, current["binding_id"]))["active"] is False


@pytest.mark.asyncio
async def test_expired_original_sid_requires_real_login_not_a_new_cookie(client, memory):
    db, _, settings = memory
    db.get(UserSession, "10").created_at = utcnow() - timedelta(
        days=settings.refresh_token_days + 1
    )
    db.commit()
    response = await bootstrap(client, settings)
    assert response.status_code == 401 and "set-cookie" not in response.headers
    assert db.get(UserSession, "11").revoked_at is None


@pytest.mark.asyncio
async def test_disabled_unified_mode_keeps_old_bearer_chat_approval_unchanged(memory):
    db, adapter, settings = memory
    settings.unified_auth_enabled = False
    result = await ChatSsoService(adapter, settings).approve(
        bearer(settings),
        db.get(User, "1"),
        "legacy-interaction",
    )
    assert set(result) == {"approval_code", "interaction_id", "finish_url"}


@pytest.mark.asyncio
async def test_overlapping_replacements_lock_current_pointer_not_stale_cookie_sid(client, memory):
    """两标签共用旧 Cookie，后来的合法换号必须撤已经接续的新 sid，不留下并行身份。"""
    db, _, settings = memory
    await bootstrap(client, settings)
    original = client.cookies.get(COOKIE_NAME)
    first = await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    assert first.status_code == 200
    first_cookie = client.cookies.get(COOKIE_NAME)
    db.add(
        UserSession(
            id="30",
            user_id="1",
            refresh_token_hash="new-login-fixture",
            last_seen_at=utcnow(),
            created_at=utcnow(),
        )
    )
    db.commit()
    later = await client.post(
        PREFIX + "/bootstrap",
        json={"replace": True},
        headers={
            "Origin": MAIN,
            "Cookie": COOKIE_NAME + "=" + original,
            "Authorization": "Bearer " + bearer(settings, "1", "30"),
        },
    )
    assert later.status_code == 200 and later.json()["data"]["session_id"] == "30"
    current = client.cookies.get(COOKIE_NAME)
    assert current.split(".")[0] == first_cookie.split(".")[0] == original.split(".")[0]
    assert len({current, first_cookie, original}) == 3
    assert db.get(UserSession, "10").revoked_at is not None
    assert db.get(UserSession, "20").revoked_at is not None
    assert db.get(UserSession, "11").revoked_at is None
    assert db.get(UserSession, "21").revoked_at is None
    for stale in (original, first_cookie):
        state = await client.get(PREFIX + "/state", headers={"Cookie": COOKIE_NAME + "=" + stale})
        assert state.json()["data"] == {"authenticated": False, "subject": None, "auth_epoch": None}
        assert "set-cookie" not in state.headers
    assert (await client.get(PREFIX + "/state")).json()["data"]["subject"] == "1"


@pytest.mark.asyncio
async def test_stale_generation_never_adopts_current_identity_without_explicit_new_login(
    client, memory
):
    _, _, settings = memory
    await bootstrap(client, settings)
    old = client.cookies.get(COOKIE_NAME)
    await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    stale = await client.post(
        PREFIX + "/bootstrap",
        json={},
        headers={
            "Origin": MAIN,
            "Cookie": COOKIE_NAME + "=" + old,
            "Authorization": "Bearer " + bearer(settings, "2", "20"),
        },
    )
    assert stale.status_code == 401
    assert stale.json()["error"]["code"] == "unified_session_changed"
    assert "set-cookie" not in stale.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["malformed", "unknown", "expired", "consumed", "revoked"])
async def test_present_invalid_cookie_never_falls_back_to_legacy_bearer(client, memory, kind):
    """中央匿名/失效状态保留权威，不能被仍有效的旧本地账号缓存自动恢复。"""
    db, _, settings = memory
    await bootstrap(client, settings)
    pointer = db.scalar(
        select(UserSecurityToken).where(UserSecurityToken.purpose == BROWSER_PURPOSE)
    )
    cookie = client.cookies.get(COOKIE_NAME)
    if kind == "malformed":
        cookie = "not-a-browser-handle"
    elif kind == "unknown":
        cookie = "x" * 43 + "." + "y" * 43
    elif kind == "expired":
        pointer.expires_at = utcnow() - timedelta(seconds=1)
    elif kind == "consumed":
        pointer.consumed_at = utcnow()
    elif kind == "revoked":
        db.get(UserSession, "10").revoked_at = utcnow()
    db.commit()
    response = await client.post(
        PREFIX + "/bootstrap",
        json={},
        headers={
            "Origin": MAIN,
            "Cookie": COOKIE_NAME + "=" + cookie,
            "Authorization": "Bearer " + bearer(settings, "2", "20"),
        },
    )
    assert response.status_code == 401 and "set-cookie" not in response.headers
    assert db.get(UserSession, "20").revoked_at is None
    assert pointer.user_id == "1"


@pytest.mark.asyncio
async def test_replacement_rechecks_new_sid_under_lock_before_revoking_browser(
    client, memory, monkeypatch
):
    """模拟初次验凭据后新 sid 被撤销；加锁后的复核必须保留原浏览器身份。"""
    db, adapter, settings = memory
    await bootstrap(client, settings)
    original_cookie = client.cookies.get(COOKIE_NAME)
    original_pointer = UnifiedAuthService._browser_pointer
    locked = []
    original_get = adapter.get

    async def record_locks(model, key, **kwargs):
        if kwargs.get("with_for_update"):
            locked.append((model, key))
        return await original_get(model, key, **kwargs)

    async def revoke_between_validation_and_lock(service, request, **kwargs):
        db.get(UserSession, "20").revoked_at = utcnow()
        db.commit()
        return await original_pointer(service, request, **kwargs)

    monkeypatch.setattr(adapter, "get", record_locks)
    monkeypatch.setattr(UnifiedAuthService, "_browser_pointer", revoke_between_validation_and_lock)
    result = await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    assert result.status_code == 401 and "set-cookie" not in result.headers
    assert (UserSession, "20") in locked and (User, "2") in locked
    assert client.cookies.get(COOKIE_NAME) == original_cookie
    assert db.get(UserSession, "10").revoked_at is None
    monkeypatch.setattr(UnifiedAuthService, "_browser_pointer", original_pointer)
    assert (await client.get(PREFIX + "/state")).json()["data"]["subject"] == "1"


@pytest.mark.asyncio
async def test_old_ticket_with_old_cookie_generation_cannot_clear_new_cookie(client, memory):
    _, _, settings = memory
    await bootstrap(client, settings)
    old = client.cookies.get(COOKIE_NAME)
    ticket = await client.post(
        PREFIX + "/logout-ticket",
        json={"return_uri": CIRCLE + "/"},
        headers={"Origin": MAIN, "Authorization": "Bearer " + bearer(settings)},
    )
    raw = parse_qs(urlsplit(ticket.json()["data"]["logout_url"]).query)["ticket"][0]
    await bootstrap(client, settings, user_id="2", session_id="20", replace=True)
    result = await client.post(
        PREFIX + "/logout",
        json={"ticket": raw},
        headers={"Origin": MAIN, "Cookie": COOKIE_NAME + "=" + old},
    )
    assert result.status_code == 200
    assert result.json()["data"]["subject"] is None
    assert "set-cookie" not in result.headers
    assert (await client.get(PREFIX + "/state")).json()["data"]["subject"] == "2"


@pytest.mark.asyncio
async def test_unified_bridge_logout_does_not_upgrade_old_bearer_binding(memory):
    db, adapter, settings = memory
    bridge = ChatSsoService(adapter, settings)
    approved = await bridge.approve(bearer(settings), db.get(User, "1"), "old-binding-request")
    identity = await bridge.exchange(CLIENT_ID, "old-binding-request", approved["approval_code"])
    binding = await bridge.verified_binding(CLIENT_ID, identity["binding_id"])
    with pytest.raises(AuthenticationError, match="统一登录"):
        await UnifiedAuthService(adapter, settings).bridge_logout_ticket(binding, CIRCLE + "/")
    assert db.get(UserSession, "10").revoked_at is None


@pytest.mark.asyncio
async def test_invalid_persisted_browser_pointer_is_unavailable_not_anonymous(client, memory):
    db, _, settings = memory
    await bootstrap(client, settings)
    pointer = db.scalar(
        select(UserSecurityToken).where(UserSecurityToken.purpose == BROWSER_PURPOSE)
    )
    pointer.payload = '{"v":2,"sid":"20","generation":false}'
    db.commit()
    response = await client.get(PREFIX + "/state")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "invalid_unified_state"
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_credentials_main_host_guard_runs_before_body_validation(memory, monkeypatch):
    """Circle 直接调用密码/验证码入口也拒绝；不能由字段校验回显其中凭据。"""
    settings = memory[2]
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        paths = [
            route.path
            for route in app.routes
            if getattr(route, "endpoint", None)
            and route.endpoint.__name__ in auth.CREDENTIAL_ENDPOINTS
        ]
        assert len(paths) == 14
        for path in paths:
            response = await client.post(CIRCLE + path, json={"password": "must-not-echo"})
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "unified_credentials_main_only"
            assert "must-not-echo" not in response.text
            assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_credentials_main_host_and_disabled_mode_keep_old_responses(memory, monkeypatch):
    settings = memory[2]
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        main = await client.post(MAIN + "/api/v1/auth/login", json={"password": "fixture"})
        assert main.status_code == 422
        settings.unified_auth_enabled = False
        old_circle = await client.post(CIRCLE + "/api/v1/auth/login", json={"password": "fixture"})
        assert old_circle.status_code == 422
    untouched = [
        route.path
        for route in app.routes
        if getattr(route, "endpoint", None)
        and route.endpoint.__name__ not in auth.CREDENTIAL_ENDPOINTS
    ]
    assert any(path.endswith("/refresh") for path in untouched)
    assert any("/fablespace/" in path for path in untouched)
