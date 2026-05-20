# Backend Spam Prevention, Rate Limits, and Screening Contract

## Scenario: write-path throttling and screened email/IP/URL rules

### 1. Scope / Trigger

- Trigger: changing registration/login limits, topic/reply/upload/report write paths,
  screened rules, automatic spam actions, or admin moderation endpoints for anti-spam.
- Applies to:
  - `apps/api/app/services/spam.py`
  - `apps/api/app/models/moderation.py`
  - `apps/api/app/api/v1/auth.py`
  - `apps/api/app/api/v1/boards.py`
  - `apps/api/app/api/v1/topics.py`
  - `apps/api/app/api/v1/uploads.py`
  - `apps/api/app/api/v1/moderation.py`
  - Alembic revisions after `0011_spam_prevention`.

### 2. Signatures

Write-path service calls:

| Path | Service guard |
|---|---|
| `POST /auth/register` | `SpamPreventionService.enforce_registration(request, email=...)` |
| `POST /auth/login` | `enforce_login(request, account=...)` |
| `POST /boards/{slug}/topics` | `enforce_topic(request, current_user, title, raw_md)` |
| `POST /topics/{id}/posts` | `enforce_reply(request, current_user, raw_md)` |
| `PATCH /posts/{id}` | `enforce_reply(request, current_user, raw_md)` |
| `POST /uploads` / `/uploads/avatar` | `enforce_upload(request, current_user)` |
| `POST /moderation/flags` | `enforce_flag(request, current_user)` |

Admin endpoints:

| Endpoint | Auth | Contract |
|---|---|---|
| `GET /moderation/screened-rules?kind=&limit=` | admin | List rules. |
| `POST /moderation/screened-rules` | admin | Create `{ kind, value, action, note }`. |
| `DELETE /moderation/screened-rules/{rule_id}` | admin | Remove a rule. |
| `GET /moderation/spam-actions?limit=` | admin | List automatic blocks/silences/rate-limit actions. |

DB tables:

- `rate_limit_events(scope, identity_type, identity_key, user_id, ip_address, created_at)`.
- `screened_rules(kind, value, normalized_value, action, note, active, created_by_id)`.
- `spam_actions(kind, action, reason, user_id, ip_address, email, url, screened_rule_id, data)`.

Config/env:

- `RATE_LIMIT_WINDOW_SECONDS`
- `RATE_LIMIT_REGISTER_IP`, `RATE_LIMIT_REGISTER_EMAIL`
- `RATE_LIMIT_LOGIN_IP`, `RATE_LIMIT_LOGIN_ACCOUNT`
- `RATE_LIMIT_TOPIC_USER`, `RATE_LIMIT_TOPIC_IP`
- `RATE_LIMIT_REPLY_USER`, `RATE_LIMIT_REPLY_IP`
- `RATE_LIMIT_UPLOAD_USER`, `RATE_LIMIT_UPLOAD_IP`
- `RATE_LIMIT_FLAG_USER`, `RATE_LIMIT_FLAG_IP`
- `NEW_USER_LINK_LIMIT`, `NEW_USER_SCREENING_DAYS`

### 3. Contracts

- Rate limits are sliding-window DB counters. Each attempt writes `rate_limit_events`; when the
  current count is already `>= limit`, the request records a `spam_actions` row and raises
  `RateLimitError("rate_limited")`.
- Rate limit identities are scoped; e.g. `topic:user` and `topic:ip` are separate counters.
- `request_ip()` prefers `x-forwarded-for` first value, then `request.client.host`.
- Screened email rules match exact email, bare domain (`blocked.example`), or suffix rule
  (`@blocked.example`).
- Screened IP rules support exact IP and CIDR ranges through `ipaddress`.
- Screened URL rules normalize host/path and match exact host, subdomain, or URL substring.
- `screened_rules.action`:
  - `block`: record `spam_actions` and reject.
  - `silence`: set `users.status='silenced'`, write `spam_actions` and `audit_logs`, then reject.
- New users (`level == 0`, created within `NEW_USER_SCREENING_DAYS`) exceeding
  `NEW_USER_LINK_LIMIT` links are auto-silenced and blocked.
- Public errors must not include the matched rule value, URL, email, threshold, or strategy details.
  Admin-only `spam_actions` may include the matched email/URL for investigation.
- Creating/deleting screened rules writes `audit_logs` actions:
  - `screened_rule_created`
  - `screened_rule_deleted`

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Registration IP exceeds window | `429 rate_limited`; `spam_actions.kind='rate_limit'`. |
| Topic author exceeds user limit | `429 rate_limited`; no topic/post row is created. |
| Many users exceed same topic IP limit | `429 rate_limited` on the overflowing request. |
| Email matches screened domain | `403 screening_blocked`; response does not leak domain/rule. |
| IP matches screened CIDR | `403 screening_blocked`. |
| URL matches `action=block` rule | `403 screening_blocked`; user status unchanged. |
| URL matches `action=silence` rule | `403 screening_blocked`; user becomes `silenced`. |
| Non-admin manages screened rules | `403 admin_required`. |
| Duplicate rule kind/value | `409 screened_rule_exists`. |
| Admin lists spam actions | Returns newest automatic actions only to admin users. |

### 5. Good/Base/Bad Cases

- Good: `AuthService.register()` calls the spam guard before creating a pending user.
- Good: `ForumService.create_topic()` checks spam before content policy and before inserting
  `topics/posts`.
- Base: DB counters are sufficient for current MVP/tests; Redis can later replace or front the
  `rate_limit_events` table without changing route contracts.
- Bad: returning `blocked because spam.example is screened` to public clients.
- Bad: adding ad-hoc rate limit counters in routers instead of `SpamPreventionService`.
- Bad: granting screened-rule management to board moderators; it is global admin-only.

### 6. Tests Required

- `apps/api/tests/test_spam_prevention.py` must assert:
  - registration IP rate limit returns `rate_limited`;
  - topic rate limits apply both user and IP dimensions;
  - admin can create/list/delete screened rules;
  - screened email blocks registration without leaking the rule value;
  - screened URL with `silence` auto-silences the user and records spam actions;
  - audit logs include screened-rule management actions.
- Full backend regression:
  - `apps/api/.venv/Scripts/python.exe -m ruff check apps/api/app apps/api/tests apps/api/alembic`
  - `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -q --tb=short`
  - fresh Alembic upgrade through `0011_spam_prevention`.

### 7. Wrong vs Correct

#### Wrong

```python
if "spam.example" in payload.raw_md:
    raise ValidationError("screening_blocked", "spam.example is blocked")
```

#### Correct

```python
await SpamPreventionService(session).enforce_topic(
    request,
    current_user=current_user,
    title=payload.title,
    raw_md=payload.raw_md,
)
```

#### Wrong

```python
if current_user.role == "moderator":
    create_screened_rule(payload)
```

#### Correct

```python
if not is_admin(current_user):
    raise PermissionDeniedError("admin_required", "Admin role required")
```
