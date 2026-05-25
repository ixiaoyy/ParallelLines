# External Integrations Backend Contract

## Scope / Trigger

Applies when changing GitHub/Zendesk/Patreon provider config, inbound external webhooks, external event retries, or issue unfurling.

## Signatures

- `GET /api/v1/admin/external-integrations` returns provider health and redacted config.
- `PUT /api/v1/admin/external-integrations/{provider}` updates `enabled` and provider config.
- `GET /api/v1/admin/external-integrations/events` lists inbound events.
- `POST /api/v1/admin/external-integrations/events/{event_id}/retry` marks failed/retryable events for retry.
- `POST /api/v1/integrations/{provider}/webhook` receives provider webhooks.
- `GET /api/v1/integrations/github/issue?url=` returns cached GitHub issue previews.

## Contracts

- Admin endpoints require `is_admin`; public webhook endpoints must verify provider signatures before storing events.
- GitHub webhook signature is `X-Hub-Signature-256: sha256=<hmac_sha256(secret, raw_body)>`.
- Provider secrets are stored in `ExternalIntegration.config` but always redacted in responses.
- Events are idempotent by `(provider, event_id)` and keep `retry_count`, `max_retries`, `next_retry_at`, and `status`.
- GitHub `issues` events update cached issue preview metadata for onebox/unfurl calls.

## Validation Matrix

| Case | Expected |
|---|---|
| Missing required provider config | Health status `misconfigured` with issue keys. |
| Invalid GitHub signature | `external_webhook_signature_invalid` / 403. |
| Duplicate delivery id | Existing event reused; no duplicate row. |
| Retry exhausted | Retry endpoint refuses or keeps event non-runnable. |

## Tests

Downgraded roadmap scope: `pytest tests/test_external_integrations.py -q` plus focused ruff on integration files.
