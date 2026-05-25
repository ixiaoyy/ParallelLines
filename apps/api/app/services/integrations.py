from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.integration import (
    ApiKey,
    ExternalIntegration,
    ExternalIntegrationEvent,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.integrations import (
    EXTERNAL_INTEGRATION_PROVIDERS,
    EXTERNAL_INTEGRATION_SECRET_KEYS,
    WEBHOOK_ALLOWED_EVENTS,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ExternalIntegrationEventResponse,
    ExternalIntegrationResponse,
    ExternalIntegrationUpdateRequest,
    ExternalWebhookResponse,
    GitHubIssuePreviewResponse,
    WebhookDeliveryResponse,
    WebhookEndpointCreateRequest,
    WebhookEndpointCreateResponse,
    WebhookEndpointResponse,
    integration_health_issues,
)
from app.services.background_jobs import BackgroundJobService

API_KEY_PREFIX = "plk_"
WEBHOOK_SECRET_PREFIX = "whsec_"
WEBHOOK_RETRY_BASE_SECONDS = 60
WEBHOOK_TIMEOUT_SECONDS = 5
GITHUB_ISSUE_URL_PATTERN = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:[/?#].*)?$"
)


@dataclass(frozen=True)
class WebhookHttpResult:
    status_code: int
    body_excerpt: str


class IntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_api_keys(self, current_user: User, *, limit: int = 100) -> list[ApiKeyResponse]:
        self._require_admin(current_user)
        rows = list(
            await self.session.scalars(
                select(ApiKey).order_by(desc(ApiKey.created_at)).limit(limit)
            )
        )
        return [ApiKeyResponse.from_model(row) for row in rows]

    async def create_api_key(
        self,
        payload: ApiKeyCreateRequest,
        current_user: User,
    ) -> ApiKeyCreateResponse:
        self._require_admin(current_user)
        owner = None
        if payload.owner_user_id:
            owner = await self.session.get(User, payload.owner_user_id)
            if owner is None:
                raise NotFoundError("user_not_found", "User not found")
        token = self.generate_api_token()
        api_key = ApiKey(
            name=payload.name.strip(),
            token_prefix=token[:16],
            token_hash=hash_api_token(token),
            scopes=list(payload.scopes),
            key_type="personal" if owner else "admin",
            owner_user_id=owner.id if owner else None,
            created_by_id=current_user.id,
            expires_at=payload.expires_at,
            note=payload.note.strip() if payload.note else None,
        )
        self.session.add(api_key)
        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action="api_key_created",
            target_type="api_key",
            target_id=api_key.id,
            data={"name": api_key.name, "scopes": api_key.scopes, "key_type": api_key.key_type},
        )
        await self.session.commit()
        await self.session.refresh(api_key)
        return ApiKeyCreateResponse(api_key=ApiKeyResponse.from_model(api_key), token=token)

    async def disable_api_key(self, key_id: str, current_user: User) -> ApiKeyResponse:
        self._require_admin(current_user)
        api_key = await self.session.get(ApiKey, key_id)
        if api_key is None:
            raise NotFoundError("api_key_not_found", "API key not found")
        if api_key.disabled_at is None:
            api_key.disabled_at = utcnow()
            api_key.disabled_by_id = current_user.id
            self._add_audit_log(
                actor_id=current_user.id,
                action="api_key_disabled",
                target_type="api_key",
                target_id=api_key.id,
                data={"name": api_key.name, "token_prefix": api_key.token_prefix},
            )
            await self.session.commit()
            await self.session.refresh(api_key)
        return ApiKeyResponse.from_model(api_key)

    async def authenticate_api_key(self, token: str | None, *, required_scope: str) -> ApiKey:
        raw_token = (token or "").strip()
        if not raw_token:
            raise AuthenticationError("api_key_required", "API key is required")
        api_key = await self.session.scalar(
            select(ApiKey).where(ApiKey.token_hash == hash_api_token(raw_token))
        )
        if api_key is None or api_key.disabled_at is not None or self._expired(api_key.expires_at):
            raise AuthenticationError("api_key_invalid", "API key is invalid or expired")
        if not api_key_has_scope(api_key.scopes or [], required_scope):
            raise PermissionDeniedError("api_key_scope_required", "API key scope is required")
        api_key.last_used_at = utcnow()
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key

    async def list_webhooks(
        self,
        current_user: User,
        *,
        limit: int = 100,
    ) -> list[WebhookEndpointResponse]:
        self._require_admin(current_user)
        rows = list(
            await self.session.scalars(
                select(WebhookEndpoint).order_by(desc(WebhookEndpoint.created_at)).limit(limit)
            )
        )
        return [WebhookEndpointResponse.from_model(row) for row in rows]

    async def create_webhook(
        self,
        payload: WebhookEndpointCreateRequest,
        current_user: User,
    ) -> WebhookEndpointCreateResponse:
        self._require_admin(current_user)
        secret = self.generate_webhook_secret()
        endpoint = WebhookEndpoint(
            name=payload.name.strip(),
            url=payload.url.strip(),
            secret=secret,
            events=list(payload.events),
            active=True,
            created_by_id=current_user.id,
            note=payload.note.strip() if payload.note else None,
        )
        self.session.add(endpoint)
        await self.session.flush()
        self._add_audit_log(
            actor_id=current_user.id,
            action="webhook_created",
            target_type="webhook_endpoint",
            target_id=endpoint.id,
            data={"name": endpoint.name, "url": endpoint.url, "events": endpoint.events},
        )
        await self.session.commit()
        await self.session.refresh(endpoint)
        return WebhookEndpointCreateResponse(
            webhook=WebhookEndpointResponse.from_model(endpoint),
            secret=secret,
        )

    async def disable_webhook(self, webhook_id: str, current_user: User) -> WebhookEndpointResponse:
        self._require_admin(current_user)
        endpoint = await self.session.get(WebhookEndpoint, webhook_id)
        if endpoint is None:
            raise NotFoundError("webhook_not_found", "Webhook endpoint not found")
        if endpoint.active:
            endpoint.active = False
            endpoint.disabled_at = utcnow()
            endpoint.disabled_by_id = current_user.id
            self._add_audit_log(
                actor_id=current_user.id,
                action="webhook_disabled",
                target_type="webhook_endpoint",
                target_id=endpoint.id,
                data={"name": endpoint.name, "url": endpoint.url},
            )
            await self.session.commit()
            await self.session.refresh(endpoint)
        return WebhookEndpointResponse.from_model(endpoint)

    async def list_webhook_deliveries(
        self,
        current_user: User,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[WebhookDeliveryResponse]:
        self._require_admin(current_user)
        statement = (
            select(WebhookDelivery)
            .options(selectinload(WebhookDelivery.endpoint))
            .order_by(desc(WebhookDelivery.created_at))
            .limit(limit)
        )
        if status:
            statement = statement.where(WebhookDelivery.status == status)
        rows = list(await self.session.scalars(statement))
        return [WebhookDeliveryResponse.from_model(row) for row in rows]

    async def enqueue_event(
        self,
        event_type: str,
        payload: dict[str, object],
        *,
        commit: bool = False,
    ) -> list[WebhookDelivery]:
        if event_type not in WEBHOOK_ALLOWED_EVENTS:
            return []
        endpoints = list(
            await self.session.scalars(
                select(WebhookEndpoint).where(WebhookEndpoint.active.is_(True))
            )
        )
        matching = [
            endpoint for endpoint in endpoints if event_matches(endpoint.events, event_type)
        ]
        deliveries: list[WebhookDelivery] = []
        service = BackgroundJobService(self.session)
        event_id = stable_event_id(event_type, payload)
        for endpoint in matching:
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                endpoint=endpoint,
                event_type=event_type,
                payload=payload,
                status="pending",
                attempt_count=0,
                max_attempts=3,
                next_attempt_at=utcnow(),
            )
            self.session.add(delivery)
            await self.session.flush()
            deliveries.append(delivery)
            await service.enqueue(
                "deliver_webhook",
                queue="webhooks",
                payload={"delivery_id": delivery.id},
                idempotency_key=f"webhook:{endpoint.id}:{event_type}:{event_id}",
                priority=40,
                max_attempts=1,
                commit=False,
            )
        if commit:
            await self.session.commit()
        return deliveries

    async def deliver_webhook(self, delivery_id: str) -> dict[str, object]:
        delivery = await self.session.scalar(
            select(WebhookDelivery)
            .options(selectinload(WebhookDelivery.endpoint))
            .where(WebhookDelivery.id == delivery_id)
        )
        if delivery is None:
            raise NotFoundError("webhook_delivery_not_found", "Webhook delivery not found")
        endpoint = delivery.endpoint
        if not endpoint.active:
            delivery.status = "disabled"
            delivery.last_error = "Webhook endpoint is disabled"
            delivery.next_attempt_at = None
            await self.session.flush()
            return {"delivery_id": delivery.id, "status": delivery.status}

        delivery.attempt_count += 1
        body = json_dumps_bytes(
            {
                "id": delivery.id,
                "event": delivery.event_type,
                "created_at": delivery.created_at.isoformat(),
                "payload": delivery.payload,
            }
        )
        timestamp = str(int(utcnow().timestamp()))
        signature = webhook_signature(endpoint.secret, body, timestamp)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ParallelLines-Webhooks/0.1",
            "X-ParallelLines-Delivery": delivery.id,
            "X-ParallelLines-Event": delivery.event_type,
            "X-ParallelLines-Timestamp": timestamp,
            "X-ParallelLines-Signature": signature,
        }

        try:
            result = await asyncio.to_thread(
                _post_json,
                endpoint.url,
                body,
                headers,
                WEBHOOK_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            return await self._mark_delivery_failure(delivery, error=str(exc) or type(exc).__name__)

        delivery.last_status_code = result.status_code
        delivery.response_body_excerpt = result.body_excerpt
        if 200 <= result.status_code < 300:
            delivery.status = "succeeded"
            delivery.delivered_at = utcnow()
            delivery.last_error = None
            delivery.next_attempt_at = None
            await self.session.flush()
            return {"delivery_id": delivery.id, "status": delivery.status}
        return await self._mark_delivery_failure(
            delivery,
            error=f"receiver returned HTTP {result.status_code}",
        )

    async def list_external_integrations(
        self,
        current_user: User,
    ) -> list[ExternalIntegrationResponse]:
        self._require_admin(current_user)
        rows = list(await self.session.scalars(select(ExternalIntegration)))
        by_provider = {row.provider: row for row in rows}
        return [
            ExternalIntegrationResponse.from_model(by_provider.get(provider), provider)
            for provider in sorted(EXTERNAL_INTEGRATION_PROVIDERS)
        ]

    async def update_external_integration(
        self,
        provider: str,
        payload: ExternalIntegrationUpdateRequest,
        current_user: User,
    ) -> ExternalIntegrationResponse:
        self._require_admin(current_user)
        provider = self._normalize_external_provider(provider)
        integration = await self.session.scalar(
            select(ExternalIntegration).where(ExternalIntegration.provider == provider)
        )
        if integration is None:
            integration = ExternalIntegration(
                provider=provider,
                enabled=payload.enabled,
                config={},
                created_by_id=current_user.id,
            )
            self.session.add(integration)
        integration.enabled = payload.enabled
        integration.config = merge_external_config(integration.config or {}, payload.config)
        integration.updated_by_id = current_user.id
        integration.last_checked_at = utcnow()
        integration.last_error = None
        self._add_audit_log(
            actor_id=current_user.id,
            action="external_integration_updated",
            target_type="external_integration",
            target_id=provider,
            data={"provider": provider, "enabled": integration.enabled},
        )
        await self.session.commit()
        await self.session.refresh(integration)
        return ExternalIntegrationResponse.from_model(integration, provider)

    async def list_external_events(
        self,
        current_user: User,
        *,
        provider: str | None = None,
        limit: int = 100,
    ) -> list[ExternalIntegrationEventResponse]:
        self._require_admin(current_user)
        statement = (
            select(ExternalIntegrationEvent)
            .order_by(desc(ExternalIntegrationEvent.created_at))
            .limit(limit)
        )
        if provider:
            statement = statement.where(
                ExternalIntegrationEvent.provider == self._normalize_external_provider(provider)
            )
        rows = list(await self.session.scalars(statement))
        return [ExternalIntegrationEventResponse.from_model(row) for row in rows]

    async def handle_external_webhook(
        self,
        provider: str,
        body: bytes,
        headers: dict[str, str | None],
    ) -> ExternalWebhookResponse:
        provider = self._normalize_external_provider(provider)
        if provider != "github":
            raise ValidationError(
                "external_provider_webhook_unsupported", "Provider webhook is not supported yet"
            )
        integration = await self._enabled_external_integration(provider)
        secret = str((integration.config or {}).get("webhook_secret") or "")
        if not secret:
            raise ValidationError(
                "external_integration_misconfigured", "GitHub webhook secret is missing"
            )
        signature = headers.get("x-hub-signature-256")
        if not verify_github_signature(secret, body, signature):
            raise PermissionDeniedError(
                "external_webhook_signature_invalid", "Invalid webhook signature"
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("external_webhook_invalid_json", "Invalid webhook JSON") from exc
        if not isinstance(payload, dict):
            raise ValidationError(
                "external_webhook_invalid_payload", "Webhook payload must be an object"
            )

        event_id = str(headers.get("x-github-delivery") or payload.get("id") or "")
        event_type = str(headers.get("x-github-event") or payload.get("event") or "")
        if not event_id or not event_type:
            raise ValidationError("external_webhook_invalid_payload", "Missing event id or type")
        existing = await self.session.scalar(
            select(ExternalIntegrationEvent).where(
                ExternalIntegrationEvent.provider == provider,
                ExternalIntegrationEvent.event_id == event_id,
            )
        )
        if existing:
            return ExternalWebhookResponse(
                provider=existing.provider,
                event_id=existing.event_id,
                event_type=existing.event_type,
                status=existing.status,
                processed=existing.status in {"processed", "ignored"},
                retry_count=existing.retry_count,
            )

        event = ExternalIntegrationEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            action=safe_optional_string(payload.get("action"), 80),
            payload=redact_integration_payload(payload),
            status="pending",
            signature_valid=True,
            max_retries=3,
        )
        self.session.add(event)
        await self.session.flush()
        await self._process_external_event(event)
        self._add_audit_log(
            actor_id=None,
            action="external_integration_webhook_processed",
            target_type="external_integration_event",
            target_id=event.id,
            data={"provider": provider, "event_type": event.event_type, "status": event.status},
        )
        await self.session.commit()
        return ExternalWebhookResponse(
            provider=event.provider,
            event_id=event.event_id,
            event_type=event.event_type,
            status=event.status,
            processed=event.status in {"processed", "ignored"},
            retry_count=event.retry_count,
        )

    async def retry_external_event(
        self,
        event_id: str,
        current_user: User,
    ) -> ExternalIntegrationEventResponse:
        self._require_admin(current_user)
        event = await self.session.get(ExternalIntegrationEvent, event_id)
        if event is None:
            raise NotFoundError(
                "external_integration_event_not_found", "External integration event not found"
            )
        if event.retry_count >= event.max_retries and event.status == "failed":
            raise ValidationError(
                "external_integration_event_retry_exhausted", "Retry budget exhausted"
            )
        event.retry_count += 1
        event.status = "pending"
        event.next_retry_at = None
        await self._process_external_event(event)
        self._add_audit_log(
            actor_id=current_user.id,
            action="external_integration_event_retried",
            target_type="external_integration_event",
            target_id=event.id,
            data={
                "provider": event.provider,
                "status": event.status,
                "retry_count": event.retry_count,
            },
        )
        await self.session.commit()
        await self.session.refresh(event)
        return ExternalIntegrationEventResponse.from_model(event)

    async def unfurl_github_issue(self, url: str) -> GitHubIssuePreviewResponse:
        match = GITHUB_ISSUE_URL_PATTERN.match(url.strip())
        if not match:
            raise ValidationError("github_issue_url_invalid", "Expected a GitHub issue URL")
        owner, repo, number_text = match.groups()
        number = int(number_text)
        cached = await self._find_cached_github_issue(url.strip(), owner, repo, number)
        if cached:
            return cached
        return GitHubIssuePreviewResponse(
            owner=owner,
            repo=repo,
            number=number,
            title=f"{owner}/{repo}#{number}",
            state=None,
            url=f"https://github.com/{owner}/{repo}/issues/{number}",
            source="parsed_url",
        )

    async def _enabled_external_integration(self, provider: str) -> ExternalIntegration:
        integration = await self.session.scalar(
            select(ExternalIntegration).where(ExternalIntegration.provider == provider)
        )
        if integration is None or not integration.enabled:
            raise ValidationError(
                "external_integration_disabled", "External integration is disabled"
            )
        issues = integration_health_issues(provider, True, integration.config or {})
        if issues:
            raise ValidationError(
                "external_integration_misconfigured",
                "External integration is misconfigured",
                {"issues": issues},
            )
        return integration

    async def _process_external_event(self, event: ExternalIntegrationEvent) -> None:
        try:
            if event.provider == "github" and event.event_type == "issues":
                self._process_github_issue_event(event)
            else:
                event.status = "ignored"
                event.processed_at = utcnow()
                event.last_error = None
                event.next_retry_at = None
        except Exception as exc:
            event.last_error = (str(exc) or type(exc).__name__)[:1000]
            if event.retry_count < event.max_retries:
                event.status = "retrying"
                event.next_retry_at = utcnow() + timedelta(seconds=WEBHOOK_RETRY_BASE_SECONDS)
            else:
                event.status = "failed"
                event.next_retry_at = None

    def _process_github_issue_event(self, event: ExternalIntegrationEvent) -> None:
        issue = event.payload.get("issue") if isinstance(event.payload, dict) else None
        repository = event.payload.get("repository") if isinstance(event.payload, dict) else None
        if not isinstance(issue, dict):
            raise ValidationError(
                "github_issue_payload_invalid", "GitHub issue payload missing issue object"
            )
        html_url = safe_optional_string(issue.get("html_url"), 1024)
        title = safe_optional_string(issue.get("title"), 500)
        number = issue.get("number")
        if not html_url or not title or not isinstance(number, int):
            raise ValidationError(
                "github_issue_payload_invalid", "GitHub issue payload missing title, number, or URL"
            )
        repo_name = ""
        if isinstance(repository, dict):
            repo_name = safe_optional_string(repository.get("full_name"), 200) or ""
        event.status = "processed"
        event.processed_at = utcnow()
        event.last_error = None
        event.next_retry_at = None
        event.linked_resource_type = "github_issue"
        event.linked_resource_id = str(number)
        event.external_url = html_url
        event.title = title if not repo_name else f"{repo_name}#{number}: {title}"

    async def _find_cached_github_issue(
        self,
        url: str,
        owner: str,
        repo: str,
        number: int,
    ) -> GitHubIssuePreviewResponse | None:
        event = await self.session.scalar(
            select(ExternalIntegrationEvent)
            .where(
                ExternalIntegrationEvent.provider == "github",
                ExternalIntegrationEvent.linked_resource_type == "github_issue",
                ExternalIntegrationEvent.external_url == url,
            )
            .order_by(desc(ExternalIntegrationEvent.created_at))
        )
        if event is None:
            return None
        state = None
        issue = event.payload.get("issue") if isinstance(event.payload, dict) else None
        if isinstance(issue, dict):
            state = safe_optional_string(issue.get("state"), 40)
        title = event.title or f"{owner}/{repo}#{number}"
        prefix = f"{owner}/{repo}#{number}: "
        if title.startswith(prefix):
            title = title[len(prefix) :]
        return GitHubIssuePreviewResponse(
            owner=owner,
            repo=repo,
            number=number,
            title=title,
            state=state,
            url=event.external_url or url,
            source="webhook_cache",
        )

    def _normalize_external_provider(self, provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized not in EXTERNAL_INTEGRATION_PROVIDERS:
            raise NotFoundError("external_provider_not_found", "External provider not found")
        return normalized

    async def _mark_delivery_failure(
        self,
        delivery: WebhookDelivery,
        *,
        error: str,
    ) -> dict[str, object]:
        delivery.last_error = error[:1000]
        delivery.delivered_at = None
        if delivery.attempt_count < delivery.max_attempts:
            delivery.status = "retrying"
            delivery.next_attempt_at = utcnow() + timedelta(
                seconds=WEBHOOK_RETRY_BASE_SECONDS * max(1, delivery.attempt_count)
            )
            await BackgroundJobService(self.session).enqueue(
                "deliver_webhook",
                queue="webhooks",
                payload={"delivery_id": delivery.id},
                idempotency_key=(
                    f"webhook-delivery:{delivery.id}:attempt:{delivery.attempt_count + 1}"
                ),
                run_at=delivery.next_attempt_at,
                priority=40,
                max_attempts=1,
                commit=False,
            )
        else:
            delivery.status = "failed"
            delivery.next_attempt_at = None
        await self.session.flush()
        return {"delivery_id": delivery.id, "status": delivery.status, "error": delivery.last_error}

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _expired(self, expires_at: datetime | None) -> bool:
        if expires_at is None:
            return False
        aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        return aware <= utcnow()

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

    @staticmethod
    def generate_api_token() -> str:
        return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def generate_webhook_secret() -> str:
        return f"{WEBHOOK_SECRET_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def api_key_has_scope(scopes: list[str], required_scope: str) -> bool:
    return "*" in scopes or required_scope in scopes


def event_matches(events: list[str] | None, event_type: str) -> bool:
    selected = events or []
    return "*" in selected or event_type in selected


def stable_event_id(event_type: str, payload: dict[str, object]) -> str:
    for key in ("id", "post_id", "topic_id", "user_id", "flag_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    digest = hashlib.sha256(json_dumps_bytes({"event": event_type, "payload": payload})).hexdigest()
    return f"generated:{digest[:32]}"


def json_dumps_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


def webhook_signature(secret: str, body: bytes, timestamp: str) -> str:
    signed = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def merge_external_config(
    current: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(current)
    for key, value in incoming.items():
        if value == "********" and key in EXTERNAL_INTEGRATION_SECRET_KEYS and key in merged:
            continue
        if value is None or value == "":
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def verify_github_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(signature, expected)


def redact_integration_payload(payload: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        lower = key.lower()
        if any(secret_key in lower for secret_key in EXTERNAL_INTEGRATION_SECRET_KEYS):
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = redact_integration_payload(value)  # type: ignore[arg-type]
        elif isinstance(value, list):
            redacted[key] = value[:50]
        else:
            redacted[key] = value
    return redacted


def safe_optional_string(value: object, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped[:max_length] if stripped else None


def _post_json(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: int,
) -> WebhookHttpResult:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - admin URL.
            response_body = response.read(4096).decode("utf-8", errors="replace")
            return WebhookHttpResult(status_code=response.status, body_excerpt=response_body[:1000])
    except HTTPError as exc:
        body_excerpt = exc.read(4096).decode("utf-8", errors="replace")
        return WebhookHttpResult(status_code=exc.code, body_excerpt=body_excerpt[:1000])
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
