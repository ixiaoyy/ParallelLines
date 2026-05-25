# Mobile Push and PWA Backend Contract

## Scope / Trigger

Applies when changing Web Push subscription storage or notification preference integration.

## Signatures

- `GET /api/v1/notifications/push-subscription` returns current user's enabled subscription state.
- `POST /api/v1/notifications/push-subscription` upserts endpoint, `p256dh`, `auth`, and user-agent metadata.
- `DELETE /api/v1/notifications/push-subscription` disables current user's enabled subscriptions.

## Contracts

- Push subscriptions belong to authenticated users and are unique by endpoint.
- Deleting a subscription soft-disables rows with `enabled=false` and `disabled_at`; do not hard-delete by default.
- Response shows only `endpoint_excerpt`, never raw encryption secrets.
- Actual outbound push delivery may be added later but must honor notification/email preferences and quiet-hour rules.

## Validation Matrix

| Case | Expected |
|---|---|
| No subscription | `subscription=null`, `supported=true`. |
| Existing endpoint resubmitted | Same row re-enabled/updated. |
| User revokes | State returns `subscription=null`. |

## Tests

Downgraded roadmap scope: `pytest tests/test_push_pwa.py -q` plus focused ruff.
