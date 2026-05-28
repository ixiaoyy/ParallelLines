# Admin Site Settings, User Management, and System Panel Contract

## Scenario: Operational admin console beyond moderation queue

### 1. Scope / Trigger

- Trigger: adding or changing admin-only site settings, user management, system health,
  audit-log, or mail-log APIs.
- Applies to `app/models/admin.py`, `schemas/admin.py`, `services/admin.py`,
  `api/v1/admin.py`, `api/v1/site.py`, `services/auth.py`, `services/uploads.py`,
  Alembic migrations, and admin frontend contracts.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/site/settings` | public | Returns public settings consumed by the app shell. |
| `GET /api/v1/admin/settings` | admin | Lists all editable site settings. |
| `PUT /api/v1/admin/settings/{key}` | admin | Updates one whitelisted setting. |
| `GET /api/v1/admin/users?query=&role=&status=&limit=` | admin | Searches users by username/email and optional filters. |
| `GET /api/v1/admin/users/{user_id}` | admin | Returns one user with content counts. |
| `PUT /api/v1/admin/users/{user_id}` | admin | Updates user role/status/level fields and optional growth deltas. |
| `GET /api/v1/admin/system` | admin | Returns DB/cache/mail/worker status, stats, recent audit and mail logs. |
| `GET /api/v1/admin/background-jobs?status=&limit=` | admin | Lists queued/running/succeeded/dead jobs. |
| `GET /api/v1/admin/background-jobs/{job_id}/logs` | admin | Lists event logs for one background job. |
| `POST /api/v1/admin/backups` | admin | Enqueue a site backup artifact job. |
| `GET /api/v1/admin/backups?status=&limit=` | admin | Lists backup artifacts and statuses. |
| `GET /api/v1/admin/backups/{backup_id}/download` | admin | Downloads a succeeded backup ZIP with checksum header. |
| `DELETE /api/v1/admin/backups/{backup_id}` | admin | Deletes the local backup archive and marks metadata deleted. |
| `POST /api/v1/admin/backups/{backup_id}/restore` | admin | Non-destructive restore validation with exact confirmation. |
| `GET /api/v1/admin/exports/site` | admin | Downloads a redacted full-site data export. |
| `GET /api/v1/admin/audit-logs?limit=` | admin | Lists global admin audit logs. |
| `GET /api/v1/admin/email-logs?limit=` | admin | Lists masked recent local/dev mail logs. |

DB table:

- `site_settings`: `key`, `value` JSON, `data_type`, `category`, `description`,
  `public`, `updated_by_id`, timestamps.

Settings with request-path effects:

- `registration_enabled=false` blocks `AuthService.register` with `registration_disabled`.
- `upload_max_bytes` and `upload_max_avatar_bytes` override runtime upload size limits.
- Public brand settings include `site_title`, `site_tagline`, and `brand_primary_color`.

### 3. Contracts

- All `/admin/*` endpoints must call `is_admin(current_user)` (directly or through
  `AdminService`) and return `admin_required` / 403 for non-admins.
- `/site/settings` may expose only rows where `public=true`; never expose secrets,
  SMTP credentials, JWT keys, raw screened rules, or private logs.
- Default settings are lazily materialized from `DEFAULT_SITE_SETTINGS`; migrations
  create the table, services insert missing defaults.
- Setting updates validate by `data_type` before persistence:
  - `boolean`: exact bool;
  - `integer`: positive integer, not bool;
  - `string`: non-empty trimmed string, max 512 chars.
- Every admin write writes an `audit_logs` row in the same transaction:
  `site_setting_updated` for setting changes and `user_admin_updated` for user changes.
- User `role` remains the permission source of truth. `level` is display/growth metadata.
- User growth adjustments must call `GrowthService.adjust_user()` so
  `points_delta` / `experience_delta` write `user_point_events` and recompute level from growth value.
- Admins cannot disable their own account or remove their own admin role through
  `/admin/users/{self}`.
- Email logs exposed by the admin API must mask recipient local parts and must not
  include verification codes or one-time tokens.
- Backup and export APIs must redact password/token/secret/code fields and must not
  generate large backup files synchronously in admin request handlers.
- System health may report cache/workers as `degraded` or `unknown`; it must not fail
  the whole endpoint if Redis is down.
- System health `queue` includes unified background worker name, queue status counts, poll/batch settings,
  and retry/schedule intervals; it must not reference removed standalone workers.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Ordinary user reads `/admin/settings` | `admin_required` / 403 |
| Unknown setting key update | `site_setting_not_found` / 404 |
| Boolean setting updated with `"false"` string | `invalid_site_setting_value` / 422 |
| Upload limit set to `0` or negative | `invalid_site_setting_value` / 422 |
| `registration_enabled=false` and visitor registers | `registration_disabled` / 403 |
| Admin updates site title | Public `/site/settings` returns new title and audit row is written |
| Admin updates another user's role/status/level | User response reflects changes and `user_admin_updated` audit row exists |
| Admin sends points/growth deltas | Response reflects floored usable points/growth value, growth ledger row exists, and audit row includes before/after |
| Admin tries to suspend self | `cannot_moderate_self` / 422 |
| Redis unavailable during `/admin/system` | Endpoint still returns 200 with cache `degraded` |
| Admin queries missing background job logs | `404 background_job_not_found` |
| Ordinary user creates or downloads backup | `admin_required` / 403 |
| Backup download before success | `backup_not_ready` / 422 |

### 5. Good/Base/Bad Cases

- Good: admin changes `site_title`; frontend app shell refetches public settings and
  displays the new title without exposing admin-only settings.
- Base: admin searches a user by email, changes status to `silenced`, or applies growth deltas,
  and audit logs show before/after role/status/level/points/experience.
- Bad: router mutates a `User` row directly without `AdminService`, skipping self
  protection or audit logs.
- Bad: `/admin/system` reports old `hot_ranking` or `upload_cleanup` worker state after the unified worker is deployed.
- Bad: `/site/settings` returns upload limits or SMTP settings that are not explicitly public.

### 6. Tests Required

- `tests/test_admin.py` must assert:
  - non-admin access to admin endpoints returns 403;
  - setting update affects `/site/settings`;
  - `registration_enabled=false` blocks registration;
  - user management writes audit logs;
  - `/admin/system` returns database status, stats, masked mail logs, and queue summary;
  - `/admin/background-jobs/{job_id}/logs` returns enqueue/start/success/retry/dead logs.
- Full backend regression: `ruff check app tests alembic` and `pytest -q`.

### 7. Wrong vs Correct

#### Wrong

```python
@router.put("/admin/users/{user_id}")
async def update_user(user_id: str, session: SessionDep):
    user = await session.get(User, user_id)
    user.role = "admin"
    await session.commit()
```

#### Correct

```python
result = await AdminService(session, settings).update_user(user_id, payload, current_user)
return ApiResponse(data=result)
```
