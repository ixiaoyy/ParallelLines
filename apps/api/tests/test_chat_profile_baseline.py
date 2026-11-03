"""使用真实主站模块与内存 SQLite 验证现网身份资料基线，不访问网络或配置数据库。"""

import json
from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as SchemaValidationError
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.core.chat_sso import (
    CLIENT_ID,
    ChatSsoCore,
    SsoDenied,
    UserState,
    VerifiedLogin,
    profile_claims,
)
from app.core.exceptions import AuthenticationError, ConflictError
from app.models.user import EmailVerificationCode, User, UserSecurityToken, UserSession
from app.schemas.auth import EmailChangeConfirmRequest
from app.schemas.chat_sso import ChatSsoStateRequest, ChatSsoStateResponse
from app.services.auth import AuthService
from app.services.chat_sso import ChatSsoService, SqlChatSsoRepository

NOW = datetime(2026, 11, 3, 8, tzinfo=UTC)


class MemoryAsyncSession:
    """提供实际服务所用异步接口；仅在测试中补足 SQLite 的 BIGINT 自增差异。"""

    def __init__(self, session):
        self.sync = session
        self.ids = count(1000)

    def add(self, row):
        if isinstance(row, UserSecurityToken) and row.id is None:
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

    async def refresh(self, row):
        self.sync.refresh(row)


@pytest.fixture
def memory():
    engine = create_engine("sqlite:///:memory:")
    for model in (User, UserSession, EmailVerificationCode, UserSecurityToken):
        model.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(User(
            id="1", username="main-user", display_name="资料名", email="current@example.invalid",
            hashed_password="synthetic-non-login-hash", role="moderator", status="active",
            points_balance=42,
        ))
        session.add(UserSession(
            id="10", user_id="1", refresh_token_hash="synthetic-refresh-hash",
            last_seen_at=NOW,
        ))
        session.commit()
        yield session, MemoryAsyncSession(session)
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("proof,verified", [
    ("none", False), ("initial", True), ("wrong-email", False), ("late-initial", False),
    ("change", True), ("legacy-change", False), ("string-true", False), ("late-change", False),
])
async def test_email_requires_consumed_matching_proof(memory, proof, verified):
    session, adapter = memory
    if proof in {"initial", "wrong-email", "late-initial"}:
        session.add(EmailVerificationCode(
            id="20", user_id="1", code_hash="synthetic-code-hash",
            email="other@example.invalid" if proof == "wrong-email" else "CURRENT@example.invalid",
            sent_at=NOW - timedelta(minutes=1), consumed_at=NOW,
            expires_at=NOW - timedelta(seconds=1) if proof == "late-initial" else NOW,
        ))
    elif proof != "none":
        payload = {"new_email": "CURRENT@example.invalid"}
        if proof != "legacy-change":
            payload["email_verified"] = "true" if proof == "string-true" else True
        session.add(UserSecurityToken(
            id="21", user_id="1", purpose="email_change", email="current@example.invalid",
            token_hash="c" * 64, payload=json.dumps(payload), consumed_at=NOW,
            sent_at=NOW - timedelta(minutes=1),
            expires_at=NOW - timedelta(seconds=1) if proof == "late-change" else NOW,
        ))
    session.commit()
    user = await SqlChatSsoRepository(adapter).get_user("1")
    assert user.email_verified is verified
    assert user.email == ("current@example.invalid" if verified else None)
    assert (user.id, user.username, user.role) == ("1", "main-user", "moderator")


async def approved_binding(adapter):
    values = iter(["a" * 48, "b" * 48])
    core = ChatSsoCore(
        SqlChatSsoRepository(adapter), finish_url="https://pingxingxian.space/auth/oidc/interaction/finish",
        login_policy="active_main", clock=lambda: NOW, issue_token=lambda: next(values),
    )
    approval = await core.approve(
        VerifiedLogin("1", "10", int((NOW + timedelta(hours=1)).timestamp())),
        "interaction-fixture",
    )
    response = await core.exchange(
        client_id=CLIENT_ID, interaction_id="interaction-fixture",
        approval_code=approval["approval_code"],
    )
    return core, approval, response


@pytest.mark.asyncio
async def test_profile_is_fresh_subject_stable_and_approval_is_one_use(memory):
    session, adapter = memory
    core, approval, response = await approved_binding(adapter)
    assert (response["sub"], response["username"], response["role"]) == (
        "1", "main-user", "moderator",
    )
    # 模拟另一事务更新资料；populate_existing 必须刷新，不能用姓名/邮箱重新找账号。
    with Session(session.bind) as writer:
        writer.execute(update(User).where(User.id == "1").values(
            display_name="更新名", email="changed@example.invalid", role="admin",
        ))
        writer.commit()
    state = await core.session_state(client_id=CLIENT_ID, binding_id=response["binding_id"])
    assert state["sub"] == "1" and state["binding_id"] == response["binding_id"]
    assert (state["name"], state["username"], state["role"]) == ("更新名", "main-user", "admin")
    assert state["email"] is None and state["email_verified"] is False
    assert session.get(User, "1").points_balance == 42
    with pytest.raises(SsoDenied, match="invalid_approval"):
        await core.exchange(
            client_id=CLIENT_ID, interaction_id="interaction-fixture",
            approval_code=approval["approval_code"],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["revoked", "expired", "suspended", "disabled", "invalid-role"])
async def test_inactive_authority_returns_no_profile(memory, denial):
    session, adapter = memory
    core, _, response = await approved_binding(adapter)
    if denial == "revoked":
        session.get(UserSession, "10").revoked_at = NOW
    elif denial == "expired":
        core.clock = lambda: NOW + timedelta(hours=2)
    elif denial == "suspended":
        session.get(User, "1").status = "suspended"
    elif denial == "disabled":
        core.login_policy = "disabled"
    else:
        session.get(User, "1").role = "owner"
    session.commit()
    state = await core.session_state(client_id=CLIENT_ID, binding_id=response["binding_id"])
    typed = ChatSsoStateResponse(**state)
    assert typed.active is False and typed.sub is None
    assert typed.name is None and typed.email is None and typed.role is None
    assert typed.email_verified is False


def test_legacy_defaults_and_request_role_cannot_grant_privilege():
    assert "role" not in profile_claims(UserState("1", "active", "旧调用"))
    with pytest.raises(SsoDenied, match="invalid_main_role"):
        profile_claims(UserState("1", "active", "名字不是权限", role="root"))
    with pytest.raises(SchemaValidationError):
        ChatSsoStateRequest(client_id=CLIENT_ID, binding_id="b" * 48, role="admin")


def test_existing_bridge_guard_is_not_bypassed_by_profile_extension(memory):
    _, adapter = memory
    secret = "synthetic-bridge-secret-" + "x" * 32
    settings = SimpleNamespace(
        chat_sso_enabled=True, chat_sso_client_id=CLIENT_ID, chat_sso_bridge_secret=secret,
        chat_sso_finish_url="https://pingxingxian.space/auth/oidc/interaction/finish",
        chat_sso_login_policy="active_main", chat_sso_allowed_user_ids=[],
        chat_sso_approval_ttl_seconds=60,
    )
    service = ChatSsoService(adapter, settings)
    for supplied in (None, "Bearer wrong", "Basic " + secret):
        with pytest.raises(AuthenticationError):
            service.require_bridge(supplied)
    service.require_bridge("Bearer " + secret)


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", [False, True])
async def test_real_email_change_marks_only_redeemed_token_in_transaction(
    memory, monkeypatch, conflict,
):
    session, adapter = memory
    monkeypatch.setattr("app.services.auth.utcnow", lambda: NOW)
    if conflict:
        session.add(User(
            id="2", username="another-user", email="next@example.invalid",
            hashed_password="synthetic-non-login-hash", role="user", status="active",
        ))
    raw = "t" * 48
    auth = AuthService(adapter, SimpleNamespace(jwt_secret_key="synthetic-local-test-key"))
    good = UserSecurityToken(
        id="30", user_id="1", purpose="email_change", email="next@example.invalid",
        token_hash=auth._hash_token(raw),
        payload=json.dumps({"new_email": "next@example.invalid"}),
        sent_at=NOW, expires_at=NOW + timedelta(minutes=10),
    )
    other = UserSecurityToken(
        id="31", user_id="1", purpose="email_change", email="next@example.invalid",
        token_hash="d" * 64, payload=json.dumps({"new_email": "next@example.invalid"}),
        sent_at=NOW, expires_at=NOW + timedelta(minutes=10),
    )
    session.add_all([good, other])
    session.commit()
    if conflict:
        with pytest.raises(ConflictError):
            await auth.confirm_email_change(EmailChangeConfirmRequest(token=raw))
        # 沿用请求会话失败后的回滚边界；不把内存中已消费状态视为持久结果。
        session.rollback()
        assert session.get(User, "1").email == "current@example.invalid"
        assert session.get(UserSecurityToken, "30").consumed_at is None
    else:
        await auth.confirm_email_change(EmailChangeConfirmRequest(token=raw))
        assert json.loads(good.payload)["email_verified"] is True
        assert "email_verified" not in json.loads(other.payload)
        assert good.consumed_at is not None and other.consumed_at is not None
        profile = await SqlChatSsoRepository(adapter).get_user("1")
        assert profile.email == "next@example.invalid" and profile.email_verified is True
    assert session.scalar(select(User.role).where(User.id == "1")) == "moderator"
