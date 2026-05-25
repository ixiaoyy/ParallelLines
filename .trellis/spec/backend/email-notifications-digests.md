# Backend Email Notifications, Digests, and Inbound Webhooks Contract

## Scenario: Email reachability for forum notifications and digests

### 1. Scope / Trigger

- Trigger: changing notification email delivery, digest scheduling, email preferences, bounce/complaint handling, or inbound reply webhooks.
- Applies to `app/models/email.py`, `schemas/email.py`, `services/email_notifications.py`, `api/v1/email.py`, `workers/background_jobs.py`, email migrations, and `services/email.py`.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/api/v1/email/preferences` | user | Return current user's email preferences, creating defaults when missing |
| `PUT` | `/api/v1/email/preferences` | user | Update master email switch, per-type notification toggles, digest frequency, and quiet hours |
| `POST` | `/api/v1/email/webhooks/delivery` | webhook secret when configured | Record provider delivery/bounce/complaint/drop event |
| `POST` | `/api/v1/email/webhooks/inbound-reply` | webhook secret when configured | Record first-version inbound reply webhook payload |

Database tables:

| Table | Contract |
|---|---|
| `user_email_preferences` | One row per user with master `email_enabled`, per notification type toggles, `digest_frequency`, UTC quiet-hour window, last digest, and delivery status |
| `email_delivery_events` | Append-only provider and local sent events, without SMTP secrets or auth tokens |
| `inbound_emails` | Inbound reply webhook records with sender/topic matching status |

Background handlers:

- `create_notification` inserts a notification row and enqueues `send_notification_email` when preferences allow.
- `send_notification_email` sends one immediate notification email and records `email_delivery_events(event_type="sent")`.
- `send_digest_emails` sends due daily/weekly digests to active users with matching unread/recent notifications.

Env:

- `EMAIL_WEBHOOK_SECRET`: optional shared secret expected in `X-Email-Webhook-Secret` for email provider webhooks.
- `BACKGROUND_DIGEST_INTERVAL_SECONDS`: time bucket for enqueueing `send_digest_emails` scheduled jobs.

### 3. Contracts

- User preferences default to email enabled, replied/mentioned/liked enabled, topic/board bulk notifications disabled, and daily digest enabled.
- Preference payload fields are:
  - `email_enabled`
  - `notify_replied`
  - `notify_mentioned`
  - `notify_liked`
  - `notify_topic_new_post`
  - `notify_board_new_topic`
  - `digest_frequency: "off" | "daily" | "weekly"`
  - `quiet_hours_start: 0..23 | null`
  - `quiet_hours_end: 0..23 | null`
- Quiet hours use UTC integer hours. Both `quiet_hours_start` and `quiet_hours_end` must be non-null
  to suppress immediate notification emails. A range with `start < end` covers `[start, end)`;
  `start > end` wraps midnight; `start == end` means all-day quiet. Passing `null` for either field
  disables quiet-hour suppression.
- Request paths never perform SMTP; they enqueue or record only. SMTP happens inside background handlers.
- Notification email idempotency key is `email-notification:{notification_id}`.
- Digest jobs send only to active users whose `email_enabled=true`, `delivery_status="ok"`, and `digest_frequency != "off"`.
- Bounce/complaint/drop webhooks record an event and automatically set `email_enabled=false` for a matched user.
- Inbound reply webhook v1 records payload and matching status only; it does not create posts yet.
- Email template site settings may use simple `{placeholder}` replacement; unknown placeholders are left as text.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Missing auth on preferences | `401 invalid_token` |
| Invalid digest frequency | FastAPI/Pydantic validation error |
| User disables `notify_replied` | Reply notification row may exist, but no `notification_replied` email is sent |
| Current UTC hour is within quiet hours | Notification row may exist, but no immediate notification email job is enqueued/sent |
| Quiet hour start/end is outside 0..23 | FastAPI/Pydantic validation error |
| Quiet hour start equals end | Treat as all-day quiet; suppress immediate notification emails |
| Digest user inactive | Skipped; no digest email |
| Delivery webhook with configured wrong secret | `403 email_webhook_secret_invalid` |
| Bounce/complaint/drop for known email | Event recorded and user's email delivery disabled |
| Delivery webhook for unknown email | Event recorded with `user_id=null`; no preference row created |
| Inbound reply from unknown sender | `inbound_emails.status="unknown_sender"` |
| Inbound reply with unknown topic | `inbound_emails.status="topic_not_found"` |

### 5. Good/Base/Bad Cases

- Good: a reply creates a notification job, then a mail job, and the request returns before email delivery.
- Good: a user turns off only replied emails while still receiving mentions and digests.
- Good: a user sets quiet hours `22 -> 6`; immediate notification emails are suppressed at 02:00 UTC
  and allowed at 14:00 UTC.
- Base: provider bounce webhook pauses future mail for that address.
- Bad: calling `EmailService` directly from `ForumService` or an API route.
- Bad: treating inbound reply payload as trusted post content before the reply creation contract is implemented.

### 6. Tests Required

- Backend tests must cover:
  - reply notification email and per-type preference suppression;
  - quiet-hours suppression for non-wrapping, midnight-wrapping, and all-day ranges;
  - digest job sends only due active users with notifications;
  - delivery webhook records event and disables bounced email;
  - inbound reply webhook records accepted status.
- Quality gates: `ruff check app tests alembic`, `pytest -q`, and `docker compose config` after env/worker changes.

### 7. Wrong vs Correct

#### Wrong

```python
# Request path blocks on SMTP.
await EmailService(settings).send_message(to_email=user.email, subject=subject, body=body, kind="notification")
```

#### Correct

```python
await BackgroundJobService(session).enqueue(
    "send_notification_email",
    queue="mail",
    payload={"notification_id": notification.id},
    idempotency_key=f"email-notification:{notification.id}",
    commit=False,
)
```
