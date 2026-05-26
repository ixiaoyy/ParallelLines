from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, RateLimitError
from app.core.permissions import is_admin
from app.core.trust import trust_adjusted_limit
from app.db.base import utcnow
from app.models.moderation import AuditLog, RateLimitEvent, ScreenedRule, SpamAction
from app.models.user import User
from app.schemas.moderation import (
    ScreenedRuleCreateRequest,
    ScreenedRuleResponse,
    SpamActionResponse,
)

URL_PATTERN = re.compile(r"https?://[^\s<>\])\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class RateLimitPolicy:
    scope: str
    identity_type: str
    identity_key: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class ScreenMatch:
    rule: ScreenedRule
    value: str


class SpamPreventionService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def enforce_registration(self, request: Request | None, *, email: str) -> None:
        ip_address = request_ip(request)
        await self._enforce_screened_email(email, ip_address=ip_address)
        await self._enforce_screened_ip(ip_address)
        await self._enforce_rate_limits(
            request,
            actor=None,
            policies=[
                self._policy("register:ip", "ip", ip_address, self.settings.rate_limit_register_ip),
                self._policy(
                    "register:email",
                    "email",
                    normalize_email(email),
                    self.settings.rate_limit_register_email,
                ),
            ],
        )

    async def enforce_login(
        self,
        request: Request | None,
        *,
        account: str,
        actor: User | None = None,
    ) -> None:
        ip_address = request_ip(request)
        await self._enforce_screened_ip(ip_address)
        await self._enforce_rate_limits(
            request,
            actor=actor,
            policies=[
                self._policy("login:ip", "ip", ip_address, self.settings.rate_limit_login_ip),
                self._policy(
                    "login:account",
                    "account",
                    account.lower(),
                    self.settings.rate_limit_login_account,
                ),
            ],
        )

    async def enforce_topic(
        self,
        request: Request | None,
        *,
        current_user: User,
        title: str,
        raw_md: str,
    ) -> None:
        await self._enforce_user_write_state(current_user)
        await self._enforce_screened_ip(request_ip(request), current_user=current_user)
        await self._enforce_content_urls(current_user, f"{title}\n{raw_md}", request=request)
        await self._enforce_new_user_link_boundary(current_user, raw_md, request=request)
        await self._enforce_rate_limits(
            request,
            actor=current_user,
            policies=[
                self._policy(
                    "topic:user",
                    "user",
                    current_user.id,
                    self.settings.rate_limit_topic_user,
                ),
                self._policy(
                    "topic:ip",
                    "ip",
                    request_ip(request),
                    self.settings.rate_limit_topic_ip,
                ),
            ],
        )

    async def enforce_reply(
        self,
        request: Request | None,
        *,
        current_user: User,
        raw_md: str,
    ) -> None:
        await self._enforce_user_write_state(current_user)
        await self._enforce_screened_ip(request_ip(request), current_user=current_user)
        await self._enforce_content_urls(current_user, raw_md, request=request)
        await self._enforce_new_user_link_boundary(current_user, raw_md, request=request)
        await self._enforce_rate_limits(
            request,
            actor=current_user,
            policies=[
                self._policy(
                    "reply:user",
                    "user",
                    current_user.id,
                    self.settings.rate_limit_reply_user,
                ),
                self._policy(
                    "reply:ip",
                    "ip",
                    request_ip(request),
                    self.settings.rate_limit_reply_ip,
                ),
            ],
        )

    async def enforce_chat_message(
        self,
        request: Request | None,
        *,
        current_user: User,
        raw_text: str,
    ) -> None:
        await self._enforce_user_write_state(current_user)
        await self._enforce_screened_ip(request_ip(request), current_user=current_user)
        await self._enforce_content_urls(current_user, raw_text, request=request)
        await self._enforce_new_user_link_boundary(current_user, raw_text, request=request)
        await self._enforce_rate_limits(
            request,
            actor=current_user,
            policies=[
                self._policy(
                    "chat_message:user",
                    "user",
                    current_user.id,
                    self.settings.rate_limit_chat_message_user,
                ),
                self._policy(
                    "chat_message:ip",
                    "ip",
                    request_ip(request),
                    self.settings.rate_limit_chat_message_ip,
                ),
            ],
        )

    async def enforce_upload(self, request: Request | None, *, current_user: User) -> None:
        await self._enforce_user_write_state(current_user)
        await self._enforce_screened_ip(request_ip(request), current_user=current_user)
        await self._enforce_rate_limits(
            request,
            actor=current_user,
            policies=[
                self._policy(
                    "upload:user",
                    "user",
                    current_user.id,
                    self.settings.rate_limit_upload_user,
                ),
                self._policy(
                    "upload:ip",
                    "ip",
                    request_ip(request),
                    self.settings.rate_limit_upload_ip,
                ),
            ],
        )

    async def enforce_flag(self, request: Request | None, *, current_user: User) -> None:
        await self._enforce_user_write_state(current_user)
        await self._enforce_screened_ip(request_ip(request), current_user=current_user)
        await self._enforce_rate_limits(
            request,
            actor=current_user,
            policies=[
                self._policy(
                    "flag:user",
                    "user",
                    current_user.id,
                    self.settings.rate_limit_flag_user,
                ),
                self._policy(
                    "flag:ip",
                    "ip",
                    request_ip(request),
                    self.settings.rate_limit_flag_ip,
                ),
            ],
        )

    async def list_screened_rules(
        self,
        current_user: User,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[ScreenedRuleResponse]:
        self._require_admin(current_user)
        statement = (
            select(ScreenedRule)
            .options(selectinload(ScreenedRule.created_by))
            .order_by(desc(ScreenedRule.created_at))
            .limit(limit)
        )
        if kind:
            statement = statement.where(ScreenedRule.kind == kind)
        rules = list(await self.session.scalars(statement))
        return [ScreenedRuleResponse.from_model(rule) for rule in rules]

    async def create_screened_rule(
        self,
        payload: ScreenedRuleCreateRequest,
        current_user: User,
    ) -> ScreenedRuleResponse:
        self._require_admin(current_user)
        normalized = normalize_rule_value(payload.kind, payload.value)
        existing = await self.session.scalar(
            select(ScreenedRule).where(
                ScreenedRule.kind == payload.kind,
                ScreenedRule.normalized_value == normalized,
            )
        )
        if existing:
            raise ConflictError(
                "screened_rule_exists",
                "A screened rule already exists",
                {"kind": payload.kind},
            )

        rule = ScreenedRule(
            kind=payload.kind,
            value=payload.value.strip(),
            normalized_value=normalized,
            action=payload.action,
            note=payload.note.strip() if payload.note else None,
            active=True,
            created_by_id=current_user.id,
        )
        self.session.add(rule)
        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action="screened_rule_created",
            target_type="screened_rule",
            target_id=rule.id,
            data={"kind": rule.kind, "action": rule.action},
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return ScreenedRuleResponse.from_model(rule)

    async def delete_screened_rule(self, rule_id: str, current_user: User) -> None:
        self._require_admin(current_user)
        rule = await self.session.get(ScreenedRule, rule_id)
        if not rule:
            raise NotFoundError("screened_rule_not_found", "Screened rule not found")
        self._add_audit_log(
            actor_id=current_user.id,
            action="screened_rule_deleted",
            target_type="screened_rule",
            target_id=rule.id,
            data={"kind": rule.kind, "action": rule.action},
        )
        await self.session.execute(delete(ScreenedRule).where(ScreenedRule.id == rule.id))
        await self.session.commit()

    async def list_spam_actions(
        self,
        current_user: User,
        *,
        limit: int = 100,
    ) -> list[SpamActionResponse]:
        self._require_admin(current_user)
        actions = list(
            await self.session.scalars(
                select(SpamAction)
                .options(selectinload(SpamAction.user), selectinload(SpamAction.screened_rule))
                .order_by(desc(SpamAction.created_at))
                .limit(limit)
            )
        )
        return [SpamActionResponse.from_model(action) for action in actions]

    async def _enforce_rate_limits(
        self,
        request: Request | None,
        *,
        actor: User | None,
        policies: list[RateLimitPolicy],
    ) -> None:
        now = utcnow()
        ip_address = request_ip(request)
        for policy in policies:
            effective_limit = (
                trust_adjusted_limit(policy.limit, actor.trust_level)
                if actor is not None and policy.identity_type == "user"
                else policy.limit
            )
            cutoff = now - timedelta(seconds=policy.window_seconds)
            count = await self.session.scalar(
                select(func.count(RateLimitEvent.id)).where(
                    RateLimitEvent.scope == policy.scope,
                    RateLimitEvent.identity_key == policy.identity_key,
                    RateLimitEvent.created_at >= cutoff,
                )
            )
            self.session.add(
                RateLimitEvent(
                    scope=policy.scope,
                    identity_type=policy.identity_type,
                    identity_key=policy.identity_key,
                    user_id=actor.id if actor else None,
                    ip_address=ip_address,
                    created_at=now,
                )
            )
            if (count or 0) >= effective_limit:
                self._add_spam_action(
                    kind="rate_limit",
                    action="block",
                    reason=policy.scope,
                    user=actor,
                    ip_address=ip_address,
                    data={
                        "scope": policy.scope,
                        "identity_type": policy.identity_type,
                        "limit": effective_limit,
                        "base_limit": policy.limit,
                        "trust_level": actor.trust_level if actor else None,
                        "window_seconds": policy.window_seconds,
                    },
                )
                await self.session.commit()
                raise RateLimitError("rate_limited", "Too many requests")
        await self.session.commit()

    async def _enforce_screened_email(self, email: str, *, ip_address: str | None) -> None:
        normalized = normalize_email(email)
        rules = await self._rules_by_kind("email")
        match = next((rule for rule in rules if email_matches_rule(normalized, rule)), None)
        if match:
            await self._screening_violation(
                match,
                reason="screened_email",
                email=normalized,
                ip_address=ip_address,
            )

    async def _enforce_screened_ip(
        self,
        ip_address: str | None,
        *,
        current_user: User | None = None,
    ) -> None:
        if not ip_address:
            return
        rules = await self._rules_by_kind("ip")
        match = next((rule for rule in rules if ip_matches_rule(ip_address, rule)), None)
        if match:
            await self._screening_violation(
                match,
                reason="screened_ip",
                user=current_user,
                ip_address=ip_address,
            )

    async def _enforce_content_urls(
        self,
        current_user: User,
        text: str,
        *,
        request: Request | None,
    ) -> None:
        urls = extract_urls(text)
        if not urls:
            return
        rules = await self._rules_by_kind("url")
        for url in urls:
            match = next((rule for rule in rules if url_matches_rule(url, rule)), None)
            if match:
                await self._screening_violation(
                    match,
                    reason="screened_url",
                    user=current_user,
                    ip_address=request_ip(request),
                    url=url,
                )

    async def _enforce_new_user_link_boundary(
        self,
        current_user: User,
        raw_md: str,
        *,
        request: Request | None,
    ) -> None:
        urls = extract_urls(raw_md)
        if len(urls) < self.settings.new_user_link_limit:
            return
        if current_user.trust_level > 0:
            return
        cutoff = utcnow() - timedelta(days=self.settings.new_user_screening_days)
        if current_user.created_at < cutoff:
            return
        current_user.status = "silenced"
        self._add_spam_action(
            kind="new_user_screening",
            action="silence",
            reason="too_many_links",
            user=current_user,
            ip_address=request_ip(request),
            data={"url_count": len(urls), "link_limit": self.settings.new_user_link_limit},
        )
        self._add_audit_log(
            actor_id=None,
            action="user_status_changed",
            target_type="user",
            target_id=current_user.id,
            data={"to_status": "silenced", "reason": "new_user_screening"},
        )
        await self.session.commit()
        raise PermissionDeniedError("screening_blocked", "Request cannot be completed")

    async def _screening_violation(
        self,
        rule: ScreenedRule,
        *,
        reason: str,
        user: User | None = None,
        ip_address: str | None = None,
        email: str | None = None,
        url: str | None = None,
    ) -> None:
        if rule.action == "silence" and user is not None:
            user.status = "silenced"
            self._add_audit_log(
                actor_id=None,
                action="user_status_changed",
                target_type="user",
                target_id=user.id,
                data={"to_status": "silenced", "reason": reason, "rule_id": rule.id},
            )
        self._add_spam_action(
            kind="screened_rule",
            action=rule.action,
            reason=reason,
            user=user,
            ip_address=ip_address,
            email=email,
            url=url,
            screened_rule=rule,
            data={"rule_kind": rule.kind},
        )
        await self.session.commit()
        raise PermissionDeniedError("screening_blocked", "Request cannot be completed")

    async def _rules_by_kind(self, kind: str) -> list[ScreenedRule]:
        return list(
            await self.session.scalars(
                select(ScreenedRule).where(ScreenedRule.kind == kind, ScreenedRule.active.is_(True))
            )
        )

    async def _enforce_user_write_state(self, current_user: User) -> None:
        if current_user.status != "active":
            raise PermissionDeniedError("account_not_active", "Request cannot be completed")

    def _policy(
        self,
        scope: str,
        identity_type: str,
        identity_key: str | None,
        limit: int,
    ) -> RateLimitPolicy:
        return RateLimitPolicy(
            scope=scope,
            identity_type=identity_type,
            identity_key=identity_key or "unknown",
            limit=limit,
            window_seconds=self.settings.rate_limit_window_seconds,
        )

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_spam_action(
        self,
        *,
        kind: str,
        action: str,
        reason: str,
        user: User | None,
        ip_address: str | None,
        email: str | None = None,
        url: str | None = None,
        screened_rule: ScreenedRule | None = None,
        data: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            SpamAction(
                kind=kind,
                action=action,
                reason=reason,
                user_id=user.id if user else None,
                ip_address=ip_address,
                email=email,
                url=url,
                screened_rule_id=screened_rule.id if screened_rule else None,
                data=data or {},
            )
        )

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )


def request_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()[:64]
    if request.client is None:
        return None
    return request.client.host[:64]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_rule_value(kind: str, value: str) -> str:
    raw = value.strip().lower()
    if kind == "email":
        return raw
    if kind == "url":
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or raw).lower()
        path = (parsed.path or "").rstrip("/")
        return f"{host}{path}" if path else host
    if kind == "ip":
        try:
            if "/" in raw:
                return str(ipaddress.ip_network(raw, strict=False))
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return raw
    return raw


def email_matches_rule(email: str, rule: ScreenedRule) -> bool:
    value = rule.normalized_value
    if value.startswith("@"):
        return email.endswith(value)
    if "@" not in value:
        return email.rsplit("@", 1)[-1] == value
    return email == value


def ip_matches_rule(ip_address: str, rule: ScreenedRule) -> bool:
    try:
        ip = ipaddress.ip_address(ip_address)
        value = rule.normalized_value
        if "/" in value:
            return ip in ipaddress.ip_network(value, strict=False)
        return ip == ipaddress.ip_address(value)
    except ValueError:
        return ip_address == rule.normalized_value


def extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,;:!?") for match in URL_PATTERN.finditer(text)]


def url_matches_rule(url: str, rule: ScreenedRule) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    normalized_url = normalize_rule_value("url", url)
    rule_value = rule.normalized_value
    if not host:
        return rule_value in normalized_url
    return (
        normalized_url == rule_value
        or host == rule_value
        or host.endswith(f".{rule_value}")
        or rule_value in normalized_url
    )
