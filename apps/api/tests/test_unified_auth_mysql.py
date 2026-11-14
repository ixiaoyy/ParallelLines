"""仅显式授权的本机临时 MySQL 库：真实行锁与 RR 并发验收，不连接默认业务库。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import timedelta
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import Request, Response
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.exceptions import AppError, AuthenticationError
from app.core.security import create_token
from app.db.base import utcnow
from app.models.user import User, UserSecurityToken, UserSession
from app.schemas.unified_auth import UnifiedAuthorizeRequest, UnifiedExchangeRequest
from app.services.unified_auth import CODE_PURPOSE, COOKIE_NAME, UnifiedAuthService

MAIN = "https://pingxingxian.space"
CIRCLE = "https://forum.pingxingxian.space"
CALLBACK = CIRCLE + "/auth/unified/callback"
MODELS = (User, UserSession, UserSecurityToken)
VERIFIER = "isolated-pkce-verifier-" + "v" * 48
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


@dataclass
class Fixture:
    sessions: async_sessionmaker[AsyncSession]
    settings: Settings


def browser(cookie: str | None = None, *, circle: bool = False) -> Request:
    """构造固定来源的服务请求；不发外网，也不从真实浏览器读取 Cookie。"""
    origin = CIRCLE if circle else MAIN
    headers = [(b"host", urlsplit(origin).netloc.encode()), (b"origin", origin.encode())]
    if cookie is not None:
        headers.append((b"cookie", (COOKIE_NAME + "=" + cookie).encode()))
    return Request({"type": "http", "scheme": "https", "path": "/", "headers": headers})


def native_access(settings: Settings, sid: str = "10", uid: str = "1") -> str:
    """签发仅限此测试设置的原生 access；不保存或输出令牌。"""
    return create_token(
        subject=uid,
        token_type="access",
        session_id=sid,
        settings=settings,
        expires_delta=timedelta(minutes=5),
    )


def cookie_from(response: Response) -> str:
    parsed = SimpleCookie()
    parsed.load(response.headers["set-cookie"])
    return parsed[COOKIE_NAME].value


@pytest.fixture
async def mysql():
    """只在明确指定的空库创建/清除三张测试表；不使用应用 DATABASE_URL 或真实 .env。"""
    raw = os.environ.get("UNIFIED_MYSQL_TEST_URL")
    if not raw:
        pytest.skip("需要显式 UNIFIED_MYSQL_TEST_URL，不使用默认数据库")
    url = make_url(raw)
    if (
        url.drivername != "mysql+asyncmy"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 13316
        or not re.fullmatch(r"pl_unified_acceptance_[0-9a-f]{12}", url.database or "")
        or os.environ.get("UNIFIED_MYSQL_ALLOW_DDL") != url.database
    ):
        pytest.fail("仅允许 loopback:13316 的显式临时库，且必须用同名 DDL 授权标记")
    engine = create_async_engine(
        url,
        isolation_level="REPEATABLE READ",
        pool_size=6,
        max_overflow=0,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "read_timeout": 6},
    )
    created = False
    try:
        async with engine.begin() as connection:
            existing = await connection.scalar(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
                )
            )
            if existing:
                pytest.fail("临时库不为空，拒绝执行 DDL 或删除已有数据")
            isolation = await connection.scalar(text("SELECT @@transaction_isolation"))
            assert isolation == "REPEATABLE-READ"
            for model in MODELS:
                await connection.run_sync(model.__table__.create)
            created = True
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            for uid in ("1", "2"):
                session.add(
                    User(
                        id=uid,
                        username="acceptance-" + uid,
                        email=uid + "@example.invalid",
                        hashed_password="synthetic-not-a-login-hash",
                        status="active",
                        role="user",
                    )
                )
            for sid, uid in (("10", "1"), ("11", "1"), ("20", "2"), ("21", "2"), ("30", "1")):
                session.add(
                    UserSession(
                        id=sid,
                        user_id=uid,
                        refresh_token_hash="synthetic-not-a-refresh-token",
                        last_seen_at=utcnow(),
                        created_at=utcnow() - timedelta(minutes=1),
                    )
                )
            await session.commit()
        settings = Settings(
            _env_file=None,
            unified_auth_enabled=True,
            public_site_url=MAIN,
            public_forum_url=CIRCLE,
            jwt_secret_key="isolated-mysql-acceptance-key-not-a-real-secret",
        )
        yield Fixture(factory, settings)
    finally:
        # 仅本夹具已确认空库后创建的三张表可清理；数据库/volume 由专属容器所有者清理。
        if created:
            async with engine.begin() as connection:
                for model in reversed(MODELS):
                    await connection.run_sync(model.__table__.drop)
        await engine.dispose()


async def bootstrap(fixture: Fixture) -> str:
    async with fixture.sessions() as session:
        response = Response()
        await UnifiedAuthService(session, fixture.settings).bootstrap(
            browser(),
            response,
            native_access(fixture.settings),
            replace=False,
        )
        return cookie_from(response)


async def connection_id(session: AsyncSession) -> int:
    return int(await session.scalar(text("SELECT CONNECTION_ID()")))


async def assert_lock_wait(fixture: Fixture, thread: int) -> None:
    """最多三秒确认数据库真的进入 LOCK WAIT，不能把两个串行调用当作并发验收。"""
    async with fixture.sessions() as observer:
        async with asyncio.timeout(3):
            while True:
                state = await observer.scalar(
                    text(
                        "SELECT trx_state FROM information_schema.innodb_trx "
                        "WHERE trx_mysql_thread_id = :thread"
                    ),
                    {"thread": thread},
                )
                if state == "LOCK WAIT":
                    return
                await asyncio.sleep(0.05)


async def assert_devices(fixture: Fixture, *, current: str, revoked: set[str]) -> None:
    async with fixture.sessions() as session:
        rows = (await session.scalars(select(UserSession))).all()
        assert {row.id for row in rows if row.revoked_at is not None} == revoked
        assert (await session.get(UserSession, current)).revoked_at is None
        assert (await session.get(UserSession, "11")).revoked_at is None
        assert (await session.get(UserSession, "21")).revoked_at is None


@pytest.mark.asyncio
async def test_mysql_pointer_serializes_two_replacements_using_same_old_generation(mysql):
    """A→B 持锁时另一标签 A→新 sid30 必须等锁，然后撤销真正前一 sid20。"""
    cookie_a = await bootstrap(mysql)
    held, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    thread = 0

    class HoldPointer(UnifiedAuthService):
        async def _browser_pointer(self, request, **kwargs):
            pointer = await super()._browser_pointer(request, **kwargs)
            held.set()
            await asyncio.wait_for(release.wait(), 5)
            return pointer

    class ObservePointer(UnifiedAuthService):
        async def _browser_pointer(self, request, **kwargs):
            nonlocal thread
            thread = await connection_id(self.session)
            waiting.set()
            return await super()._browser_pointer(request, **kwargs)

    async def replace(service_type, sid, uid):
        async with mysql.sessions() as session:
            response = Response()
            result = await service_type(session, mysql.settings).bootstrap(
                browser(cookie_a),
                response,
                native_access(mysql.settings, sid, uid),
                replace=True,
            )
            return result, cookie_from(response)

    first = asyncio.create_task(replace(HoldPointer, "20", "2"))
    second = None
    try:
        await asyncio.wait_for(held.wait(), 5)
        second = asyncio.create_task(replace(ObservePointer, "30", "1"))
        await asyncio.wait_for(waiting.wait(), 5)
        await assert_lock_wait(mysql, thread)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([second] if second else [])), 8)
    assert results[0][0].session_id == "20" and results[1][0].session_id == "30"
    cookie_b, cookie_c = results[0][1], results[1][1]
    await assert_devices(mysql, current="30", revoked={"10", "20"})
    for cookie in (cookie_a, cookie_b):
        async with mysql.sessions() as session:
            assert (
                await UnifiedAuthService(session, mysql.settings).cookie_login(browser(cookie))
                is None
            )
    async with mysql.sessions() as session:
        assert (
            await UnifiedAuthService(session, mysql.settings).cookie_login(browser(cookie_c))
        ).session.id == "30"


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["session", "user"])
async def test_mysql_rr_snapshot_cannot_revive_later_revoked_new_identity(mysql, changed):
    """初次 bearer 一致性读以后撤 sid/停用户；最终锁定读取必须看见新状态并保留旧身份。"""
    cookie = await bootstrap(mysql)
    validated, release = asyncio.Event(), asyncio.Event()

    class PauseValidated(UnifiedAuthService):
        async def bearer_login(self, token, **kwargs):
            login = await super().bearer_login(token, **kwargs)
            validated.set()
            await asyncio.wait_for(release.wait(), 5)
            return login

    async def replace():
        async with mysql.sessions() as session:
            response = Response()
            with pytest.raises(AuthenticationError):
                await PauseValidated(session, mysql.settings).bootstrap(
                    browser(cookie),
                    response,
                    native_access(mysql.settings, "20", "2"),
                    replace=True,
                )
            assert "set-cookie" not in response.headers

    task = asyncio.create_task(replace())
    try:
        await asyncio.wait_for(validated.wait(), 5)
        async with mysql.sessions() as revoker:
            if changed == "session":
                await revoker.execute(
                    update(UserSession).where(UserSession.id == "20").values(revoked_at=utcnow())
                )
            else:
                await revoker.execute(update(User).where(User.id == "2").values(status="suspended"))
            await revoker.commit()
    finally:
        release.set()
        await asyncio.wait_for(task, 8)
    async with mysql.sessions() as session:
        assert (
            await UnifiedAuthService(session, mysql.settings).cookie_login(browser(cookie))
        ).session.id == "10"
    await assert_devices(mysql, current="10", revoked={"20"} if changed == "session" else set())


@pytest.mark.asyncio
async def test_mysql_pkce_same_code_concurrent_redemption_has_only_one_success(mysql):
    """实际授权码行锁阻塞第二个兑换；第一次提交后重放必须失效，不能双发成功。"""
    cookie = await bootstrap(mysql)
    async with mysql.sessions() as session:
        issued = await UnifiedAuthService(session, mysql.settings).authorize(
            browser(cookie),
            UnifiedAuthorizeRequest(
                client_id="parallellines-circle",
                redirect_uri=CALLBACK,
                state="mysql-acceptance-state",
                code_challenge=CHALLENGE,
                code_challenge_method="S256",
            ),
        )
    code = parse_qs(urlsplit(issued.redirect_url).query)["code"][0]
    payload = UnifiedExchangeRequest(
        client_id="parallellines-circle",
        redirect_uri=CALLBACK,
        code=code,
        code_verifier=VERIFIER,
    )
    held, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    thread = 0

    class HoldCode(UnifiedAuthService):
        async def _read_ticket(self, *args):
            result = await super()._read_ticket(*args)
            held.set()
            await asyncio.wait_for(release.wait(), 5)
            return result

    class ObserveCode(UnifiedAuthService):
        async def _read_ticket(self, *args):
            nonlocal thread
            thread = await connection_id(self.session)
            waiting.set()
            return await super()._read_ticket(*args)

    async def redeem(service_type):
        async with mysql.sessions() as session:
            try:
                return await service_type(session, mysql.settings).exchange(
                    browser(circle=True), payload
                )
            except AppError as error:
                return error

    first = asyncio.create_task(redeem(HoldCode))
    second = None
    try:
        await asyncio.wait_for(held.wait(), 5)
        second = asyncio.create_task(redeem(ObserveCode))
        await asyncio.wait_for(waiting.wait(), 5)
        await assert_lock_wait(mysql, thread)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([second] if second else [])), 8)
    assert results[0].session_id == "10"
    assert isinstance(results[1], AppError) and results[1].code == "invalid_unified_code"
    async with mysql.sessions() as session:
        record = await session.scalar(
            select(UserSecurityToken).where(UserSecurityToken.purpose == CODE_PURPOSE)
        )
        assert record.consumed_at is not None


@pytest.mark.asyncio
async def test_mysql_old_logout_waiting_on_account_switch_cannot_clear_new_cookie(mysql):
    """旧退出票排在换号锁后执行，只撤旧 sid，响应不得删除后来已经发行的新 Cookie。"""
    cookie_a = await bootstrap(mysql)
    async with mysql.sessions() as session:
        service = UnifiedAuthService(session, mysql.settings)
        login = await service.bearer_login(native_access(mysql.settings), lock=True)
        issued = await service.logout_ticket(login, CIRCLE + "/")
    ticket = parse_qs(urlsplit(issued.logout_url).query)["ticket"][0]
    held, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    thread = 0

    class HoldSwitch(UnifiedAuthService):
        async def _browser_pointer(self, request, **kwargs):
            pointer = await super()._browser_pointer(request, **kwargs)
            held.set()
            await asyncio.wait_for(release.wait(), 5)
            return pointer

    class ObserveLogout(UnifiedAuthService):
        async def _browser_pointer(self, request, **kwargs):
            nonlocal thread
            thread = await connection_id(self.session)
            waiting.set()
            return await super()._browser_pointer(request, **kwargs)

    async def switch():
        async with mysql.sessions() as session:
            response = Response()
            await HoldSwitch(session, mysql.settings).bootstrap(
                browser(cookie_a),
                response,
                native_access(mysql.settings, "20", "2"),
                replace=True,
            )
            return cookie_from(response)

    async def logout():
        async with mysql.sessions() as session:
            response = Response()
            result = await ObserveLogout(session, mysql.settings).logout(
                browser(cookie_a), response, ticket
            )
            assert result.ok and not result.authenticated
            assert "set-cookie" not in response.headers

    first = asyncio.create_task(switch())
    second = None
    try:
        await asyncio.wait_for(held.wait(), 5)
        second = asyncio.create_task(logout())
        await asyncio.wait_for(waiting.wait(), 5)
        await assert_lock_wait(mysql, thread)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([second] if second else [])), 8)
    async with mysql.sessions() as session:
        assert (
            await UnifiedAuthService(session, mysql.settings).cookie_login(browser(results[0]))
        ).user.id == "2"
    await assert_devices(mysql, current="20", revoked={"10"})
