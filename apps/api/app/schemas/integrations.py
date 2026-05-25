from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.integration import (
    ApiKey,
    ExternalIntegration,
    ExternalIntegrationEvent,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.schemas.common import ORMModel

API_KEY_ALLOWED_SCOPES = {
    "read",
    "topics:read",
    "topics:write",
    "webhooks:read",
    "webhooks:write",
    "admin:read",
}
WEBHOOK_ALLOWED_EVENTS = {
    "topic.created",
    "post.created",
    "user.created",
    "user.verified",
    "moderation.flag_created",
}


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=20)
    owner_user_id: str | None = Field(default=None, max_length=36)
    expires_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(scope.strip() for scope in value if scope.strip()))
        invalid = [scope for scope in unique if scope not in API_KEY_ALLOWED_SCOPES]
        if invalid:
            raise ValueError(f"invalid scopes: {', '.join(invalid)}")
        return unique


class ApiKeyResponse(ORMModel):
    id: str
    name: str
    token_prefix: str
    scopes: list[str]
    key_type: str
    owner_user_id: str | None = None
    created_by_id: str | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    disabled_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, api_key: ApiKey) -> ApiKeyResponse:
        return cls(
            id=api_key.id,
            name=api_key.name,
            token_prefix=api_key.token_prefix,
            scopes=list(api_key.scopes or []),
            key_type=api_key.key_type,
            owner_user_id=api_key.owner_user_id,
            created_by_id=api_key.created_by_id,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            disabled_at=api_key.disabled_at,
            note=api_key.note,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at,
        )


class ApiKeyCreateResponse(BaseModel):
    api_key: ApiKeyResponse
    token: str


class WebhookEndpointCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=8, max_length=1024)
    events: list[str] = Field(default_factory=list, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith(("http://", "https://")):
            raise ValueError("webhook URL must start with http:// or https://")
        return trimmed

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(event.strip() for event in value if event.strip()))
        invalid = [event for event in unique if event not in WEBHOOK_ALLOWED_EVENTS]
        if invalid:
            raise ValueError(f"invalid webhook events: {', '.join(invalid)}")
        return unique


class WebhookEndpointResponse(ORMModel):
    id: str
    name: str
    url: str
    events: list[str]
    active: bool
    created_by_id: str | None = None
    disabled_at: datetime | None = None
    disabled_by_id: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, endpoint: WebhookEndpoint) -> WebhookEndpointResponse:
        return cls(
            id=endpoint.id,
            name=endpoint.name,
            url=endpoint.url,
            events=list(endpoint.events or []),
            active=endpoint.active,
            created_by_id=endpoint.created_by_id,
            disabled_at=endpoint.disabled_at,
            disabled_by_id=endpoint.disabled_by_id,
            note=endpoint.note,
            created_at=endpoint.created_at,
            updated_at=endpoint.updated_at,
        )


class WebhookEndpointCreateResponse(BaseModel):
    webhook: WebhookEndpointResponse
    secret: str


class WebhookDeliveryResponse(ORMModel):
    id: str
    endpoint_id: str
    endpoint_name: str | None = None
    event_type: str
    status: Literal["pending", "retrying", "succeeded", "failed", "disabled"] | str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    last_status_code: int | None = None
    last_error: str | None = None
    delivered_at: datetime | None = None
    response_body_excerpt: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, delivery: WebhookDelivery) -> WebhookDeliveryResponse:
        return cls(
            id=delivery.id,
            endpoint_id=delivery.endpoint_id,
            endpoint_name=delivery.endpoint.name if delivery.endpoint else None,
            event_type=delivery.event_type,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            max_attempts=delivery.max_attempts,
            next_attempt_at=delivery.next_attempt_at,
            last_status_code=delivery.last_status_code,
            last_error=delivery.last_error,
            delivered_at=delivery.delivered_at,
            response_body_excerpt=delivery.response_body_excerpt,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )


EXTERNAL_INTEGRATION_PROVIDERS = {"github", "zendesk", "patreon"}
EXTERNAL_INTEGRATION_REQUIRED_CONFIG: dict[str, list[str]] = {
    "github": ["webhook_secret"],
    "zendesk": ["subdomain", "api_token"],
    "patreon": ["campaign_id", "webhook_secret"],
}
EXTERNAL_INTEGRATION_SECRET_KEYS = {
    "api_token",
    "access_token",
    "client_secret",
    "patreon_token",
    "webhook_secret",
}


class ExternalIntegrationUpdateRequest(BaseModel):
    enabled: bool = False
    config: dict[str, object] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, object]) -> dict[str, object]:
        if len(value) > 50:
            raise ValueError("too many integration config keys")
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            normalized_key = key.strip().lower()
            if not normalized_key or len(normalized_key) > 80:
                raise ValueError("invalid integration config key")
            if isinstance(item, str):
                cleaned[normalized_key] = item.strip()[:2000]
            elif isinstance(item, (bool, int, float)) or item is None:
                cleaned[normalized_key] = item
            else:
                raise ValueError("integration config values must be scalar")
        return cleaned


class ExternalIntegrationResponse(ORMModel):
    provider: str
    enabled: bool
    config: dict[str, object]
    required_config: list[str]
    status: Literal["disabled", "healthy", "misconfigured", "error"] | str
    issues: list[str]
    last_checked_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_model(
        cls, integration: ExternalIntegration | None, provider: str
    ) -> ExternalIntegrationResponse:
        config = dict(integration.config or {}) if integration else {}
        enabled = bool(integration.enabled) if integration else False
        issues = integration_health_issues(provider, enabled, config)
        if not enabled:
            status = "disabled"
        elif issues:
            status = "misconfigured"
        elif integration and integration.last_error:
            status = "error"
        else:
            status = "healthy"
        return cls(
            provider=provider,
            enabled=enabled,
            config=redact_external_config(config),
            required_config=EXTERNAL_INTEGRATION_REQUIRED_CONFIG.get(provider, []),
            status=status,
            issues=issues,
            last_checked_at=integration.last_checked_at if integration else None,
            last_error=integration.last_error if integration else None,
            updated_at=integration.updated_at if integration else None,
        )


class ExternalIntegrationEventResponse(ORMModel):
    id: str
    provider: str
    event_id: str
    event_type: str
    action: str | None = None
    status: str
    signature_valid: bool
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None = None
    processed_at: datetime | None = None
    last_error: str | None = None
    linked_resource_type: str | None = None
    linked_resource_id: str | None = None
    external_url: str | None = None
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, event: ExternalIntegrationEvent) -> ExternalIntegrationEventResponse:
        return cls(
            id=event.id,
            provider=event.provider,
            event_id=event.event_id,
            event_type=event.event_type,
            action=event.action,
            status=event.status,
            signature_valid=event.signature_valid,
            retry_count=event.retry_count,
            max_retries=event.max_retries,
            next_retry_at=event.next_retry_at,
            processed_at=event.processed_at,
            last_error=event.last_error,
            linked_resource_type=event.linked_resource_type,
            linked_resource_id=event.linked_resource_id,
            external_url=event.external_url,
            title=event.title,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )


class ExternalWebhookResponse(BaseModel):
    provider: str
    event_id: str
    event_type: str
    status: str
    processed: bool
    retry_count: int = 0


class GitHubIssuePreviewResponse(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    state: str | None = None
    url: str
    source: Literal["webhook_cache", "parsed_url"]


def redact_external_config(config: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in config.items():
        if key in EXTERNAL_INTEGRATION_SECRET_KEYS and value not in (None, ""):
            redacted[key] = "********"
        else:
            redacted[key] = value
    return redacted


def integration_health_issues(provider: str, enabled: bool, config: dict[str, object]) -> list[str]:
    if not enabled:
        return []
    issues: list[str] = []
    for key in EXTERNAL_INTEGRATION_REQUIRED_CONFIG.get(provider, []):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"missing_config:{key}")
    return issues
