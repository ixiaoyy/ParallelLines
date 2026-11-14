"""以现有 UserSession 为唯一权威的浏览器 SSO；不新建账号库或跨域刷新令牌。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlsplit

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat_sso import MAIN_ROLES, VerifiedLogin
from app.core.config import Settings
from app.core.exceptions import AppError, AuthenticationError, PermissionDeniedError
from app.core.security import create_token, decode_token
from app.db.base import as_utc_datetime, utcnow
from app.models.user import User, UserSecurityToken, UserSession
from app.schemas.unified_auth import (
    UnifiedAccessResponse,
    UnifiedAuthorizeRequest,
    UnifiedAuthorizeResponse,
    UnifiedExchangeRequest,
    UnifiedLogoutResponse,
    UnifiedLogoutTicketResponse,
    UnifiedStateResponse,
)
from app.schemas.users import UserPublic

COOKIE_NAME = "__Host-pl-unified"
BROWSER_PURPOSE = "unified_browser"
CODE_PURPOSE = "unified_auth_code"
LOGOUT_PURPOSE = "unified_logout"
ACCESS_SECONDS = 300
TICKET_SECONDS = 60
OPAQUE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
ID_PATTERN = re.compile(r"^[1-9][0-9]{0,31}$")


@dataclass(frozen=True)
class BrowserLogin:
    """已从数据库复核的单设备会话及其到期时间，不代表其他产品授权。"""

    user: User
    session: UserSession
    expires_at: datetime


@dataclass(frozen=True)
class BrowserPointer:
    """浏览器句柄对应的串行指针；旧代际不能读取指针后来绑定的另一个身份。"""

    record: UserSecurityToken
    handle: str
    generation: str
    supplied_generation: str
    session_id: str

    @property
    def matches(self) -> bool:
        return hmac.compare_digest(self.generation, self.supplied_generation)


class UnifiedAuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        """绑定只读/单次票据事务；新功能显式启用且仅允许已配置 HTTPS 主站与圈子。"""

        if not settings.unified_auth_enabled:
            raise PermissionDeniedError("unified_auth_unavailable", "统一登录尚未启用")
        self.session = session
        self.settings = settings
        self.main_origin = self.configured_origin(settings.public_site_url, settings)
        self.circle_origin = self.configured_origin(settings.public_forum_url, settings)
        self.cookie_secure = urlsplit(self.main_origin).scheme == "https"
        self.cookie_name = COOKIE_NAME if self.cookie_secure else "pl-unified-local"
        if self.main_origin == self.circle_origin:
            raise PermissionDeniedError("unified_auth_unavailable", "统一登录来源配置无效")

    @staticmethod
    def configured_origin(value: str | None, settings: Settings) -> str:
        """接受 HTTPS，或显式启用的 loopback HTTP；不从请求头生成信任来源。"""

        parsed = urlsplit(value or "")
        loopback_http = (
            settings.unified_auth_allow_loopback_http
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        )
        if (
            (parsed.scheme != "https" and not loopback_http)
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise PermissionDeniedError("unified_auth_unavailable", "统一登录来源配置无效")
        return parsed.geturl().rstrip("/")

    def require_main_host(self, request: Request) -> None:
        """中央 Cookie 接口只在主站主机提供；反代内层 HTTP 不参与来源选择。"""

        if request.url.netloc.lower() != urlsplit(self.main_origin).netloc.lower():
            raise PermissionDeniedError("unified_origin_denied", "请通过主站完成此操作")

    def require_origin(self, request: Request, origin: str) -> None:
        """浏览器写入同时要求精确 Origin/Host，拒绝缺失、null 或任意转发头。"""

        if (
            request.headers.get("origin") != origin
            or request.url.netloc.lower() != urlsplit(origin).netloc.lower()
        ):
            raise PermissionDeniedError("unified_origin_denied", "登录请求来源无效")

    def require_main_write(self, request: Request) -> None:
        """所有依赖中央 Cookie 的写入同时校验主站 Host 和精确主站 Origin。"""

        self.require_main_host(request)
        self.require_origin(request, self.main_origin)

    def _epoch(self, session_id: str) -> str:
        """返回不泄露 sid 的稳定 opaque 版本标记；不能单独用于鉴权。"""

        return self._hash("browser-epoch", session_id)

    def _hash(self, purpose: str, value: str) -> str:
        """按用途隔离票据摘要；数据库与 URL 不保存主站刷新令牌。"""

        return hmac.new(
            self.settings.jwt_secret_key.encode(), f"{purpose}:{value}".encode(), hashlib.sha256
        ).hexdigest()

    async def _session_login(
        self,
        user_id: str,
        session_id: str,
        *,
        lock: bool = False,
    ) -> BrowserLogin:
        """复核单个用户/sid/当前状态及最长寿命；写事务可锁定该 sid 防止并发复活。"""

        if not ID_PATTERN.fullmatch(user_id) or not ID_PATTERN.fullmatch(session_id):
            raise AuthenticationError("unified_login_required", "请先登录主站")
        row = await self.session.get(
            UserSession,
            session_id,
            populate_existing=True,
            with_for_update=lock,
        )
        user = await self.session.get(User, user_id, populate_existing=True, with_for_update=lock)
        if (
            row is None
            or user is None
            or row.user_id != user.id
            or row.revoked_at is not None
            or user.status != "active"
            or user.role not in MAIN_ROLES
        ):
            raise AuthenticationError("unified_login_required", "请先登录主站")
        expiry = as_utc_datetime(row.created_at) + timedelta(days=self.settings.refresh_token_days)
        if expiry <= utcnow():
            raise AuthenticationError("unified_login_required", "请重新登录主站")
        return BrowserLogin(user, row, expiry)

    async def bearer_login(self, token: str, *, lock: bool = False) -> BrowserLogin:
        """仅接受现有 Main access JWT 且必须带 sid；旧无 sid 会话须重新登录一次。"""

        data = decode_token(token, settings=self.settings)
        if not isinstance(data.get("sid"), str) or not isinstance(data.get("sub"), str):
            raise AuthenticationError("unified_login_required", "请重新登录主站")
        return await self._session_login(data["sub"], data["sid"], lock=lock)

    async def _browser_pointer(
        self, request: Request, *, lock: bool = False
    ) -> BrowserPointer | None:
        """仅读独立 opaque 句柄摘要；换号事务可锁定真正当前 sid，不采信旧 Cookie 的身份。"""

        raw = request.cookies.get(self.cookie_name, "")
        pieces = raw.split(".")
        if len(pieces) != 2 or any(not OPAQUE_PATTERN.fullmatch(part) for part in pieces):
            return None
        statement = select(UserSecurityToken).where(
            UserSecurityToken.purpose == BROWSER_PURPOSE,
            UserSecurityToken.token_hash == self._hash(BROWSER_PURPOSE, pieces[0]),
        )
        if lock:
            statement = statement.with_for_update()
        record = await self.session.scalar(statement.execution_options(populate_existing=True))
        if record is None:
            return None
        try:
            payload = json.loads(record.payload or "{}")
        except (TypeError, ValueError) as error:
            raise AppError(
                "invalid_unified_state", "统一登录状态暂不可用", status_code=503
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 2
            or not isinstance(payload.get("sid"), str)
            or not ID_PATTERN.fullmatch(payload["sid"])
            or not isinstance(payload.get("generation"), str)
            or not OPAQUE_PATTERN.fullmatch(payload["generation"])
        ):
            raise AppError("invalid_unified_state", "统一登录状态暂不可用", status_code=503)
        return BrowserPointer(record, pieces[0], payload["generation"], pieces[1], payload["sid"])

    async def _pointer_login(
        self, pointer: BrowserPointer | None, *, lock: bool = False
    ) -> BrowserLogin | None:
        """只有当前有效代际能读取身份；数据库故障不被降级为匿名成功。"""

        if (
            pointer is None
            or not pointer.matches
            or pointer.record.consumed_at is not None
            or as_utc_datetime(pointer.record.expires_at) <= utcnow()
        ):
            return None
        try:
            login = await self._session_login(pointer.record.user_id, pointer.session_id, lock=lock)
        except AuthenticationError:
            return None
        return BrowserLogin(
            login.user,
            login.session,
            min(login.expires_at, as_utc_datetime(pointer.record.expires_at)),
        )

    async def cookie_login(self, request: Request, *, lock: bool = False) -> BrowserLogin | None:
        """按中央句柄及当前代际复核 sid；不接受主站 access/refresh JWT 作为 Cookie。"""

        return await self._pointer_login(await self._browser_pointer(request, lock=lock), lock=lock)

    def state_for(self, login: BrowserLogin | None) -> UnifiedStateResponse:
        """只投影 iframe 所需身份状态；不包含令牌、邮箱或其他个人资料。"""

        return UnifiedStateResponse(
            authenticated=login is not None,
            subject=login.user.id if login else None,
            auth_epoch=self._epoch(login.session.id) if login else None,
        )

    def _access(self, login: BrowserLogin) -> UnifiedAccessResponse:
        """发行同一 sid 的五分钟标准 access JWT；不能用来换刷新令牌或替代 OIDC token。"""

        seconds = min(ACCESS_SECONDS, int((login.expires_at - utcnow()).total_seconds()))
        if seconds <= 0:
            raise AuthenticationError("unified_login_required", "请重新登录主站")
        return UnifiedAccessResponse(
            **self.state_for(login).model_dump(),
            access_token=create_token(
                subject=login.user.id,
                token_type="access",
                settings=self.settings,
                expires_delta=timedelta(seconds=seconds),
                session_id=login.session.id,
            ),
            expires_in=seconds,
            session_id=login.session.id,
            user=UserPublic.model_validate(login.user),
        )

    def set_cookie(
        self, response: Response, login: BrowserLogin, handle: str, generation: str
    ) -> None:
        """只写主机专属 HttpOnly Cookie；不设置 Domain，也不共享主站 refresh/master token。"""

        seconds = max(0, int((login.expires_at - utcnow()).total_seconds()))
        response.set_cookie(
            self.cookie_name,
            handle + "." + generation,
            max_age=seconds,
            secure=self.cookie_secure,
            httponly=True,
            samesite="lax",
            path="/",
        )

    def clear_cookie(self, response: Response) -> None:
        """清除同属性的中央 Cookie，不触及其他设备或其他域的存储。"""

        response.delete_cookie(
            self.cookie_name,
            path="/",
            secure=self.cookie_secure,
            httponly=True,
            samesite="lax",
        )

    async def bootstrap(
        self,
        request: Request,
        response: Response,
        token: str | None,
        *,
        replace: bool,
    ) -> UnifiedAccessResponse:
        """迁移现有 sid 或续发短 access；只有显式登录替换才撤销此前浏览器 sid。"""

        self.require_main_write(request)
        # 先验证新凭据再取浏览器指针锁；无效换号请求不能撤销当前 sid。
        proposed = await self.bearer_login(token) if replace and token else None
        if replace and proposed is None:
            raise AuthenticationError("unified_login_required", "请先登录主站")
        pointer = await self._browser_pointer(request, lock=True)
        previous = await self._pointer_login(pointer, lock=not replace)
        if previous is not None and not replace:
            return self._access(previous)
        if pointer is not None and not pointer.matches and not replace:
            raise AuthenticationError("unified_session_changed", "主站身份已变化，请重新接续登录")
        # 已存在的中央 Cookie 无论过期、撤销或损坏都不能被旧本地 bearer 自动覆盖。
        # 只有完全没有 Cookie 的首次迁移，或完成真实登录后的显式 replace 可以建会话。
        if not replace and self.cookie_name in request.cookies:
            raise AuthenticationError("unified_login_required", "请重新登录主站")
        if not token:
            raise AuthenticationError("unified_login_required", "请先登录主站")
        proposed = proposed or await self.bearer_login(token)
        # 两个标签持有同一旧 Cookie 时按指针中的最新 sid 串行换号，始终撤真正前一身份。
        for sid in sorted(
            {proposed.session.id, pointer.session_id if pointer else proposed.session.id}, key=int
        ):
            await self.session.get(UserSession, sid, populate_existing=True, with_for_update=True)
        login = await self._session_login(proposed.user.id, proposed.session.id, lock=True)
        # 先确认新身份可以完整返回，再撤旧 sid；校验失败不得让旧浏览器被动退出。
        result = self._access(login)
        if pointer is not None and pointer.session_id != login.session.id:
            old = await self.session.get(UserSession, pointer.session_id, populate_existing=True)
            if old is not None and old.user_id == pointer.record.user_id:
                old.revoked_at = old.revoked_at or utcnow()
        if pointer is None:
            handle, generation = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self.session.add(
                UserSecurityToken(
                    user_id=login.user.id,
                    purpose=BROWSER_PURPOSE,
                    token_hash=self._hash(BROWSER_PURPOSE, handle),
                    payload=json.dumps(
                        {"v": 2, "sid": login.session.id, "generation": generation},
                        separators=(",", ":"),
                    ),
                    sent_at=utcnow(),
                    expires_at=login.expires_at,
                )
            )
        else:
            handle = pointer.handle
            generation = (
                pointer.generation
                if (pointer.session_id == login.session.id and pointer.record.consumed_at is None)
                else secrets.token_urlsafe(32)
            )
            pointer.record.user_id = login.user.id
            pointer.record.payload = json.dumps(
                {"v": 2, "sid": login.session.id, "generation": generation}, separators=(",", ":")
            )
            pointer.record.expires_at = login.expires_at
            pointer.record.consumed_at = None
        await self.session.commit()
        self.set_cookie(response, login, handle, generation)
        return result

    async def _ticket(
        self,
        login: BrowserLogin,
        purpose: str,
        payload: dict[str, object],
    ) -> str:
        """保存固定用途的一分钟单次码；原文只返回调用方，复用既有 security token 表。"""

        raw = secrets.token_urlsafe(32)
        now = utcnow()
        self.session.add(
            UserSecurityToken(
                user_id=login.user.id,
                purpose=purpose,
                token_hash=self._hash(purpose, raw),
                payload=json.dumps(
                    {"v": 1, "sid": login.session.id, **payload}, separators=(",", ":")
                ),
                sent_at=now,
                expires_at=min(now + timedelta(seconds=TICKET_SECONDS), login.expires_at),
            )
        )
        await self.session.commit()
        return raw

    async def authorize(
        self,
        request: Request,
        payload: UnifiedAuthorizeRequest,
    ) -> UnifiedAuthorizeResponse:
        """为唯一 Circle 公共客户端签发绑定回调及 S256 的单次码，不直接跨域传 token。"""

        self.require_main_write(request)
        if payload.redirect_uri != self.circle_origin + "/auth/unified/callback":
            raise AppError("invalid_unified_redirect", "登录回调无效")
        login = await self.cookie_login(request, lock=True)
        if login is None:
            raise AuthenticationError("unified_login_required", "请先登录主站")
        code = await self._ticket(
            login,
            CODE_PURPOSE,
            {
                "client_id": payload.client_id,
                "redirect_uri": payload.redirect_uri,
                "challenge": payload.code_challenge,
                "auth_epoch": self._epoch(login.session.id),
            },
        )
        return UnifiedAuthorizeResponse(
            redirect_url=payload.redirect_uri
            + "?"
            + urlencode(
                {
                    "code": code,
                    "state": payload.state,
                }
            )
        )

    async def _read_ticket(
        self, raw: str, purpose: str, error: str
    ) -> tuple[
        UserSecurityToken,
        dict[str, object],
    ]:
        """按用途读取并锁定单次码；无效输入不回显，具体消费仍用条件 UPDATE 防重放。"""

        if not OPAQUE_PATTERN.fullmatch(raw):
            raise AppError(error, "登录操作已失效，请重试")
        record = await self.session.scalar(
            select(UserSecurityToken)
            .where(
                UserSecurityToken.purpose == purpose,
                UserSecurityToken.token_hash == self._hash(purpose, raw),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record is None or record.consumed_at or as_utc_datetime(record.expires_at) <= utcnow():
            raise AppError(error, "登录操作已失效，请重试")
        try:
            payload = json.loads(record.payload or "{}")
        except (TypeError, ValueError) as exc:
            raise AppError(error, "登录操作已失效，请重试") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or not isinstance(
                payload.get("sid"),
                str,
            )
        ):
            raise AppError(error, "登录操作已失效，请重试")
        return record, payload

    async def _consume(self, record: UserSecurityToken, error: str) -> None:
        """在原事务中条件消费一次；失败不伪装成功，也不增加其他会话副作用。"""

        now = utcnow()
        result = await self.session.execute(
            update(UserSecurityToken)
            .where(
                UserSecurityToken.id == record.id,
                UserSecurityToken.consumed_at.is_(None),
                UserSecurityToken.expires_at > now,
            )
            .values(consumed_at=now)
            # 条件消费交给数据库，不让 ORM 在内存比较 MySQL 无时区 DATETIME 与 UTC now。
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise AppError(error, "登录操作已失效，请重试")

    async def exchange(
        self,
        request: Request,
        payload: UnifiedExchangeRequest,
    ) -> UnifiedAccessResponse:
        """Circle 只用 verifier 兑换同一 sid 的短 access；错回调、来源、重放和撤销都拒绝。"""

        self.require_origin(request, self.circle_origin)
        error = "invalid_unified_code"
        row, data = await self._read_ticket(payload.code, CODE_PURPOSE, error)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(payload.code_verifier.encode("ascii")).digest())
            .decode()
            .rstrip("=")
        )
        if (
            data.get("client_id") != payload.client_id
            or data.get("redirect_uri") != payload.redirect_uri
            or payload.redirect_uri != self.circle_origin + "/auth/unified/callback"
            or not isinstance(data.get("challenge"), str)
            or not hmac.compare_digest(data["challenge"], challenge)
        ):
            raise AppError(error, "登录操作已失效，请重试")
        login = await self._session_login(row.user_id, str(data["sid"]), lock=True)
        if data.get("auth_epoch") != self._epoch(login.session.id):
            raise AppError(error, "登录操作已失效，请重试")
        result = self._access(login)
        await self._consume(row, error)
        await self.session.commit()
        return result

    def _return_uri(self, value: str) -> str:
        """退出仅回四个固定站点根页；FableSpace、任意路径、查询及片段不在本次范围。"""

        allowed = {
            self.main_origin + "/",
            self.circle_origin + "/",
            "https://chat.pingxingxian.space/",
            "https://api.pingxingxian.space/",
        }
        if value not in allowed:
            raise AppError("invalid_unified_redirect", "退出返回地址无效")
        return value

    async def logout_ticket(
        self,
        login: BrowserLogin,
        return_uri: str,
    ) -> UnifiedLogoutTicketResponse:
        """为已复核的单个 sid 签发有限退出票据，不在出票时提前撤销任何会话。"""

        target = self._return_uri(return_uri)
        ticket = await self._ticket(login, LOGOUT_PURPOSE, {"return_uri": target})
        return UnifiedLogoutTicketResponse(
            logout_url=self.main_origin + "/auth/unified/logout?" + urlencode({"ticket": ticket}),
            expires_in=TICKET_SECONDS,
        )

    async def bridge_logout_ticket(
        self,
        binding: VerifiedLogin,
        return_uri: str,
    ) -> UnifiedLogoutTicketResponse:
        """桥已验证 binding 后再复核原 sid；过期绑定不能借此撤销其他会话。"""

        if not binding.unified_browser:
            raise AuthenticationError("unified_login_required", "请先接续主站统一登录")
        login = await self._session_login(binding.user_id, binding.session_id, lock=True)
        return await self.logout_ticket(login, return_uri)

    async def logout(
        self,
        request: Request,
        response: Response,
        ticket: str | None,
    ) -> UnifiedLogoutResponse:
        """撤销票据或当前 Cookie 的单个 sid；旧 RP 票据不能清除已换号的新 Cookie。"""

        self.require_main_write(request)
        pointer = await self._browser_pointer(request, lock=True)
        current = await self._pointer_login(pointer, lock=True)
        target_id = current.session.id if current else None
        target_user = current.user.id if current else None
        return_url = None
        if ticket is not None:
            row, data = await self._read_ticket(
                ticket,
                LOGOUT_PURPOSE,
                "invalid_unified_logout_ticket",
            )
            target_id, target_user = str(data["sid"]), row.user_id
            return_url = self._return_uri(str(data.get("return_uri", "")))
            await self._consume(row, "invalid_unified_logout_ticket")
        clear_current = pointer is not None and pointer.matches and pointer.session_id == target_id
        if target_id is not None:
            # 已撤销的票据目标也能安全完成清理，但绝不扩散到该用户的其他 sid。
            target = await self.session.get(UserSession, target_id, with_for_update=True)
            if target is None or target.user_id != target_user:
                raise AppError("invalid_unified_logout_ticket", "退出操作已失效")
            target.revoked_at = target.revoked_at or utcnow()
        if clear_current:
            pointer.record.consumed_at = utcnow()
        if target_id is not None or clear_current:
            await self.session.commit()
        # 旧代际/旧 RP 票据不能以 Set-Cookie 删除后来已经换号的浏览器身份。
        if clear_current:
            self.clear_cookie(response)
            current = None
        return UnifiedLogoutResponse(**self.state_for(current).model_dump(), return_url=return_url)
