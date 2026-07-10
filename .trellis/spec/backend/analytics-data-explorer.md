# Analytics and Data Explorer Contract

## Scenario: Admin analytics, preset data explorer reports, and audited CSV export

### 1. Scope / Trigger

- Trigger: changing admin analytics endpoints, metric definitions, preset report rows, or CSV
  export behavior.
- Applies to `schemas/analytics.py`, `services/analytics.py`, `api/v1/analytics.py`, admin
  router registration, audit logs, and generated OpenAPI snapshots.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/admin/analytics?start_date=&end_date=` | admin | Returns totals, daily series, and top lists. |
| `GET /api/v1/admin/analytics/reports` | admin | Lists safe preset report definitions. |
| `GET /api/v1/admin/analytics/reports/{report_id}` | admin | Runs one preset report for the date range. |
| `GET /api/v1/admin/analytics/reports/{report_id}/export.csv` | admin | Exports one preset report and writes audit log. |

Metric fields:

- Daily: `dau`, `registrations`, `topics`, `posts`, `likes`, `flags`; `registrations`
  counts only users where `users.is_persona = false`.
- Totals: `dau`, `mau`, `registrations`, `topics`, `posts`, `likes`, `flags`;
  `registrations` is the sum of the filtered daily registration series.

Preset reports:

- `daily_activity`
- `top_topics`
- `top_users`
- `flags_by_reason`

### 3. Contracts

- All analytics endpoints must use the admin permission gate and return `admin_required` / 403 for
  non-admin users.
- Date range defaults to the last 30 days and is capped at 366 days.
- Invalid reversed or oversized ranges return `invalid_analytics_range` / 422.
- Data Explorer is preset-only. Do not accept arbitrary SQL from the client.
- CSV export must write `audit_logs.action="analytics_csv_exported"` in the same request.
- Report rows must use ORM-built SQL expressions and bound parameters; never concatenate user input.
- Private-message topics are excluded from public/top-topic analytics.
- `users.is_persona` is the durable account-identity flag for growth metrics. Ordinary registration
  defaults it to `false`; persona seed, living-forum, frontier-news, and migration-import paths must
  persist `true`. Do not infer persona identity from username patterns, roles, or email domains.
- The overview series, overview totals, `daily_activity` report, and its CSV export must all reuse
  the same persona-excluding registration query so the displayed and exported values cannot drift.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Ordinary user opens analytics | `admin_required` / 403 |
| Unknown report id | `analytics_report_not_found` / 404 |
| `start_date > end_date` | `invalid_analytics_range` / 422 |
| Range over 366 days | `invalid_analytics_range` / 422 |
| Export CSV | `text/csv` response and audit row is persisted |
| Empty range | Returns zero-valued series and empty top lists, not 500 |
| Persona and ordinary user register on the same day | Only the ordinary user increments `registrations` in overview, report, and CSV. |

### 5. Good/Base/Bad Cases

- Good: admin requests today's range and sees registrations/topics/posts/likes/flags plus top lists.
- Base: admin runs `daily_activity`, exports CSV, and audit console can show
  `analytics_csv_exported`.
- Bad: exposing a raw SQL textarea or interpolating `q`/report ids into SQL.
- Bad: frontend-only permission hiding while backend report endpoints are readable by moderators/users.

### 6. Tests Required

- Default roadmap smoke: `pytest tests/test_analytics.py -q`.
- Assertions:
  - non-admin gets 403;
  - overview totals and daily series include ordinary registrations but exclude `is_persona=true` rows;
  - preset report returns rows;
  - `daily_activity.registrations` matches the filtered overview series exactly;
  - CSV export returns CSV and writes audit log.
- Run `ruff check` on touched analytics service/router/schema/test files.

### 7. Wrong vs Correct

#### Wrong

```python
rows = await session.execute(text(f"select * from {payload.table}"))
```

#### Correct

```python
report = await AnalyticsService(session).run_report(current_user, "daily_activity", ...)
```

Preset reports keep Data Explorer useful without arbitrary SQL risk.
