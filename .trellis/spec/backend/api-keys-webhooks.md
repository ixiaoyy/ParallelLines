# API Keys and Webhooks Contract

## Scenario: Scoped external API access and signed outbound webhooks

### 1. Scope / Trigger

- Trigger: adding or changing API key authentication, integration scopes, outbound webhook events,
  webhook signatures, retry behavior, or delivery logs.
- Applies to `app/models/integration.py`, `app/schemas/integrations.py`,
  `app/services/integrations.py`, `app/api/v1/integrations.py`,
  `app/workers/background_jobs.py`, Alembic migrations, and event producers in auth/forum/moderation
  services.

### 2. Signatures

Database tables:

| Table | Fields | Contract |
|---|---|---|
| `api_keys` | `name`, `token_prefix`, `token_hash`, `scopes`, `key_type`, `owner_user_id`, `created_by_id`, `last_used_at`, `expires_at`, `disabled_at`, `disabled_by_id`, `note` | Stores key metadata and SHA-256 token hash only; plaintext token is returned once at creation. |
| `webhook_endpoints` | `name`, `url`, `secret`, `events`, `active`, `created_by_id`, `disabled_at`, `disabled_by_id`, `note` | Stores active/inactive outbound endpoints and their signing secret. API responses never list `secret`; creation returns it once. |
| `webhook_deliveries` | `endpoint_id`, `event_type`, `payload`, `status`, `attempt_count`, `max_attempts`, `next_attempt_at`, `last_status_code`, `last_error`, `delivered_at`, `response_body_excerpt` | Durable delivery log and retry state for each endpoint/event payload. |

Admin APIs:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/admin/api-keys?limit=` | List key metadata for admins. |
| `POST` | `/api/v1/admin/api-keys` | Create scoped API key and return plaintext token once. |
| `POST` | `/api/v1/admin/api-keys/{key_id}/disable` | Disable a key without deleting audit history. |
| `GET` | `/api/v1/admin/webhooks?limit=` | List webhook endpoints without secrets. |
| `POST` | `/api/v1/admin/webhooks` | Create endpoint and return signing secret once. |
| `POST` | `/api/v1/admin/webhooks/{webhook_id}/disable` | Disable endpoint and stop future deliveries. |
| `GET` | `/api/v1/admin/webhook-deliveries?status=&limit=` | Inspect recent delivery logs. |

Integration API:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/integrations/me` | `X-API-Key` or `Authorization: Bearer <api-key>` with `read` scope | Smoke endpoint for external clients and scope enforcement. |

Service and worker signatures:

- `IntegrationService.create_api_key(payload, current_user) -> ApiKeyCreateResponse`
- `IntegrationService.authenticate_api_key(token, required_scope) -> ApiKey`
- `IntegrationService.create_webhook(payload, current_user) -> WebhookEndpointCreateResponse`
- `IntegrationService.enqueue_event(event_type, payload, commit=False) -> list[WebhookDelivery]`
- `IntegrationService.deliver_webhook(delivery_id) -> dict[str, object]`
- Background job handler: `deliver_webhook` on queue `webhooks` with payload
  `{ "delivery_id": "<webhook_deliveries.id>" }`.

Allowed values:

- API key scopes: `read`, `topics:read`, `topics:write`, `webhooks:read`, `webhooks:write`,
  `admin:read`.
- Webhook events: `topic.created`, `post.created`, `user.created`, `user.verified`,
  `moderation.flag_created`.

Outbound webhook headers:

| Header | Value |
|---|---|
| `X-ParallelLines-Delivery` | Delivery row ID. |
| `X-ParallelLines-Event` | Event type. |
| `X-ParallelLines-Timestamp` | Unix timestamp used for signing. |
| `X-ParallelLines-Signature` | `v1=<hmac_sha256(secret, timestamp + "." + json_body)>`. |

### 3. Contracts

- Admin-only integration endpoints must call the normal authenticated user dependency and enforce
  `admin_required`; API key authentication is only for external integration endpoints.
- Empty `scopes` is valid metadata but must not authorize protected integration APIs. Missing,
  disabled, expired, or unknown tokens return `401`; known keys without the required scope return
  `403 api_key_scope_required`.
- Only store API token hashes. Never log or return plaintext API tokens after creation.
- `WebhookEndpointResponse` must not expose `secret`; only `WebhookEndpointCreateResponse` reveals
  the secret once so admins can configure receivers.
- Request-path services enqueue webhook delivery jobs with `commit=False` inside the caller
  transaction. Direct administrative/test enqueue may pass `commit=True`.
- Webhook retry state lives on `webhook_deliveries`. The background job row uses `max_attempts=1`
  so queue-level retries do not duplicate integration-level retry scheduling.
- Deliveries transition:
  - `pending` before first worker run;
  - `succeeded` for HTTP 2xx;
  - `retrying` after network/non-2xx failure while attempts remain;
  - `failed` when attempts are exhausted;
  - `disabled` if the endpoint is disabled before delivery.
- Event producers must keep payloads small and non-secret. Use IDs, slugs, titles, status, and
  timestamps; do not include passwords, raw tokens, cookies, or large rendered bodies.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Non-admin calls `/admin/api-keys` or `/admin/webhooks` | `403 admin_required`. |
| Create key with invalid scope | `422 validation_error`; no row created. |
| Create key with empty scopes | Row created; `/integrations/me` returns `403 api_key_scope_required`. |
| Disabled or expired key authenticates | `401 api_key_invalid`. |
| Missing key on integration endpoint | `401 api_key_required`. |
| Create webhook with non-HTTP URL or invalid event | `422 validation_error`; no endpoint created. |
| Receiver returns non-2xx or network error | Delivery records status/error, increments attempt, schedules retry until max attempts. |
| Endpoint disabled before delivery | Delivery status becomes `disabled`; no HTTP request is sent. |
| Admin disables key/webhook twice | Operation is idempotent and returns current disabled/inactive state. |

### 5. Good/Base/Bad Cases

- Good: `ForumService.create_topic` enqueues `topic.created` with `commit=False`; the same
  transaction creates the topic, delivery row, and `deliver_webhook` job.
- Good: webhook signatures are verified by recomputing `webhook_signature(secret, body, timestamp)`
  against `X-ParallelLines-Signature`.
- Base: admin creates a `read` key, calls `/api/v1/integrations/me`, then disables the key and
  receives `api_key_invalid` on the next call.
- Bad: sending the webhook HTTP request synchronously from a topic/reply/user request handler.
- Bad: exposing `webhook_endpoints.secret` from list/detail APIs or writing API token plaintext into
  audit logs.

### 6. Tests Required

- Downgraded roadmap scope: run backend lint and focused tests for integration permissions/signing:
  `ruff check app tests/test_api_keys_webhooks.py` and
  `pytest tests/test_api_keys_webhooks.py -q`.
- Permission assertions:
  - empty-scope key returns `api_key_scope_required`;
  - read-scope key succeeds;
  - disabled key returns `api_key_invalid`.
- Webhook assertions:
  - signature header equals HMAC over the exact JSON body and timestamp;
  - failing receiver creates `retrying` delivery with `attempt_count=1`, `last_error`, and a queued
    retry job.
- Run `py_compile` or equivalent on the Alembic migration after adding integration tables.

### 7. Wrong vs Correct

#### Wrong

```python
# Runs network I/O inside the request transaction and can duplicate retries.
await _post_json(endpoint.url, payload, headers, timeout_seconds=30)
```

#### Correct

```python
await IntegrationService(session).enqueue_event(
    "topic.created",
    {"topic_id": topic.id, "title": topic.title},
    commit=False,
)
```

#### Wrong

```python
return {"token": api_key.token_hash, "secret": endpoint.secret}
```

#### Correct

```python
return WebhookEndpointResponse.from_model(endpoint)  # no secret outside create response
```
