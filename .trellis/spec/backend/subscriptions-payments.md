# Subscriptions and Payments Contract

## Scenario: Paid membership plans, signed provider webhooks, and entitlement state

### 1. Scope / Trigger

- Trigger: changing subscription plans, user subscription state, payment webhook signatures,
  billing event logs, or paid entitlement checks.
- Applies to `models/payment.py`, `schemas/payments.py`, `services/payments.py`,
  `api/v1/payments.py`, runtime settings, and Alembic migrations.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/subscriptions/plans` | public | Lists active membership plans. |
| `GET /api/v1/subscriptions/me` | user | Returns current subscription status and active entitlements. |
| `GET /api/v1/admin/payments/events` | admin | Lists recent payment webhook events. |
| `POST /api/v1/payments/webhooks/{provider}` | signed webhook | Processes provider event payload. |

Webhook signature:

- Header: `X-ParallelLines-Signature`
- Value: hex HMAC-SHA256 digest or `sha256=<digest>`
- Secret: `Settings.payment_webhook_secret`

Supported event types:

- `checkout.session.completed` / `invoice.paid`: activate subscription.
- `invoice.payment_failed`: mark subscription `past_due`.
- `customer.subscription.deleted` / `subscription.expired`: expire subscription.

### 3. Contracts

- Frontend never grants paid entitlements directly. Only signed webhook processing can activate a
  subscription.
- Invalid webhook signatures return `payment_webhook_signature_invalid` / 403 and must not create
  payment events.
- Webhook events are idempotent by `(provider, event_id)`.
- `UserSubscriptionResponse.entitlements` is empty unless status is active and
  `current_period_end` is in the future.
- Expired active subscriptions are marked `expired` when read by `/subscriptions/me`.
- Payment event payload storage must redact obvious secret/token/card/payment method fields.
- Admin billing event list uses the same admin gate as other `/admin/*` routes.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Bad/missing signature | `payment_webhook_signature_invalid` / 403 |
| Invalid JSON | `payment_webhook_invalid_json` / 422 |
| Missing event id/type | `payment_webhook_invalid_payload` / 422 |
| Duplicate event id | Returns processed response without duplicating event |
| Successful paid event | User subscription active, entitlements returned |
| Period end in past | `/subscriptions/me` returns `expired` and no entitlements |
| Non-admin reads payment events | `admin_required` / 403 |

### 5. Good/Base/Bad Cases

- Good: provider sends signed `checkout.session.completed`; backend activates `supporter` plan.
- Good: failed payment event marks the existing provider subscription `past_due` for admin tracking.
- Base: user opens billing page and sees current status plus plan entitlements.
- Bad: frontend sets `paid_member=true` after a client-side checkout redirect without webhook
  verification.
- Bad: accepting unsigned provider payloads in local/test and forgetting to enforce signatures.

### 6. Tests Required

- Default roadmap smoke: `pytest tests/test_payments.py -q`.
- Assertions:
  - plan list materializes default plan;
  - invalid signature is rejected;
  - signed success webhook grants entitlements;
  - expired period revokes entitlements;
  - non-admin cannot read payment events.
- Run `ruff check` on touched payment model/schema/service/router/migration/test files.

### 7. Wrong vs Correct

#### Wrong

```python
subscription.status = "active"  # from frontend callback
```

#### Correct

```python
await PaymentService(session, settings).handle_webhook(provider, body, signature)
```

The service owns signature validation, idempotency, subscription mutation, and event records.
