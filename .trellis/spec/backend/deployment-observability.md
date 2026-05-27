# Deployment, CI, and Observability Contract

## Scenario: Runnable local stack and quality gate automation

### 1. Scope / Trigger

- Trigger: adding Docker Compose, CI, seed data, Playwright smoke tests, API metrics, worker runtime, and operations documentation.
- Applies to `docker-compose.yml`, `apps/api/Dockerfile`, `apps/web/Dockerfile`, `.github/workflows/ci.yml`, `README.md`, `app/main.py`, `app/seed.py`, and `app/workers/`.

### 2. Signatures

Runtime services:

| Service | Command / Port | Contract |
|---|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | Runs migrations/seed in Compose before serving |
| `web` | `pnpm --dir apps/web preview --host 0.0.0.0 --port 5174` | Static Vite preview built with `VITE_API_BASE_URL` |
| `worker` | `python -m app.workers.background_jobs` | Unified queue worker for mail, notifications, hot ranking, upload cleanup, and session cleanup |
| `mysql` | `mysql:8.4` | MySQL source of truth |
| `redis` | `redis:7-alpine` | Cache/coordination dependency |

Email verification env:

| Env | Contract |
|---|---|
| `EMAIL_DELIVERY_MODE` | `memory` for local/test only, `smtp` for real delivery. Production must not run `memory`. |
| `SMTP_HOST` / `SMTP_PORT` | Required when `EMAIL_DELIVERY_MODE=smtp`. |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Optional SMTP auth credentials; never log or commit. |
| `SMTP_FROM_EMAIL` | Sender address used for verification emails. |
| `SMTP_USE_TLS` / `SMTP_USE_SSL` | TLS mode; `SMTP_USE_TLS=true` starts STARTTLS unless SSL is enabled. |
| `SMTP_TIMEOUT_SECONDS` | Timeout used by the background email handler when `EMAIL_DELIVERY_MODE=smtp`. |
| `EMAIL_WEBHOOK_SECRET` | Optional shared secret required in `X-Email-Webhook-Secret` for email delivery/inbound webhooks. |
| `EMAIL_VERIFICATION_CODE_TTL_MINUTES` | Verification code expiry. |
| `EMAIL_VERIFICATION_RESEND_SECONDS` | Minimum resend interval. |
| `EMAIL_VERIFICATION_MAX_ATTEMPTS` | Invalid-code attempts before lockout. |
| `PASSWORD_RESET_TOKEN_TTL_MINUTES` | Password reset token expiry. |
| `EMAIL_CHANGE_TOKEN_TTL_MINUTES` | Email-change confirmation token expiry. |
| `TWO_FACTOR_CHALLENGE_MINUTES` | Login second-factor challenge token expiry. |
| `TWO_FACTOR_ISSUER` | Issuer label embedded in TOTP `otpauth://` URLs. |
| `OAUTH_ENABLED_PROVIDERS` | JSON/list of configured OAuth provider names exposed by `/auth/oauth/providers`. |
| `RATE_LIMIT_WINDOW_SECONDS` | Sliding-window size for DB-backed anti-spam counters. |
| `RATE_LIMIT_REGISTER_IP` / `RATE_LIMIT_REGISTER_EMAIL` | Registration throttle by source IP and email. |
| `RATE_LIMIT_LOGIN_IP` / `RATE_LIMIT_LOGIN_ACCOUNT` | Login throttle by source IP and account string. |
| `RATE_LIMIT_TOPIC_USER` / `RATE_LIMIT_TOPIC_IP` | Topic creation throttle by user and source IP. |
| `RATE_LIMIT_REPLY_USER` / `RATE_LIMIT_REPLY_IP` | Reply/edit throttle by user and source IP. |
| `RATE_LIMIT_UPLOAD_USER` / `RATE_LIMIT_UPLOAD_IP` | Upload throttle by user and source IP. |
| `RATE_LIMIT_FLAG_USER` / `RATE_LIMIT_FLAG_IP` | Report/flag throttle by user and source IP. |
| `NEW_USER_LINK_LIMIT` / `NEW_USER_SCREENING_DAYS` | New-user high-link auto-silence boundary. |

Upload storage env:

| Env | Contract |
|---|---|
| `UPLOAD_STORAGE_BACKEND` | `local` for current MVP; `s3` is reserved config and must not be silently treated as local in production docs. |
| `UPLOAD_STORAGE_PATH` | Local storage root; Docker Compose mounts it as a persistent `upload-data` volume. |
| `UPLOAD_CDN_BASE_URL` | Optional future CDN base URL for public objects. |
| `UPLOAD_S3_BUCKET` / `UPLOAD_S3_REGION` / `UPLOAD_S3_ENDPOINT_URL` | Reserved S3-compatible object storage config. |
| `UPLOAD_MAX_BYTES` / `UPLOAD_MAX_AVATAR_BYTES` | Single-file limits for post attachments and avatars. |
| `UPLOAD_MAX_FILES_PER_POST` | Maximum number of upload URLs attachable to one post. |
| `UPLOAD_TEMPORARY_TTL_HOURS` | Expiry window for uploads not yet attached to a post. |

Backup storage env:

| Env | Contract |
|---|---|
| `BACKUP_STORAGE_PATH` | Local backup/export archive directory; API and worker must share the same persistent volume. |

Background worker env:

| Env | Contract |
|---|---|
| `BACKGROUND_JOB_POLL_SECONDS` | Unified worker poll interval. |
| `BACKGROUND_JOB_BATCH_SIZE` | Max jobs processed per worker loop. |
| `BACKGROUND_JOB_RETRY_DELAY_SECONDS` | Base retry delay for failed jobs. |
| `BACKGROUND_HOT_RANK_INTERVAL_SECONDS` | Time-bucket interval for hot-score recompute jobs. |
| `BACKGROUND_UPLOAD_CLEANUP_INTERVAL_SECONDS` | Time-bucket interval for expired temporary upload cleanup jobs. |
| `BACKGROUND_SESSION_CLEANUP_INTERVAL_SECONDS` | Time-bucket interval for stale session cleanup jobs. |
| `BACKGROUND_DIGEST_INTERVAL_SECONDS` | Time-bucket interval for email digest dispatcher jobs. |

API ops endpoints:

- `GET /healthz` returns service health JSON.
- `GET /metrics` returns Prometheus-style text counters:
  - `parallellines_requests_total`
  - `parallellines_request_duration_seconds_total`
  - `parallellines_requests_by_status_total{status="..."}`

Seed command:

- `python -m app.seed` idempotently creates demo users, boards, memberships, and starter topics.
- `python -m app.seed --if-empty` first checks for existing boards or topics and skips seeding
  when content already exists; Docker Compose uses this guarded mode during API startup.

CI commands:

- Backend: `uv sync --frozen`, `uv run ruff check app tests`, `uv run pytest -q`.
- Frontend: `pnpm install --frozen-lockfile`, `pnpm --dir apps/web lint`, `typecheck`, `build`.
- Smoke: `pnpm --dir apps/web test:smoke` against a running API/web pair.

### 3. Contracts

- Docker Compose must start a usable local environment from an empty volume with `docker compose up --build`.
- API startup in Compose must run `alembic upgrade head` before `python -m app.seed --if-empty`.
- Worker image reuses the API build and must not run migrations.
- API and `worker` must share the same `UPLOAD_STORAGE_PATH` and `BACKUP_STORAGE_PATH`
  volumes; otherwise DB metadata will point at files the cleanup handler, backup
  handler, or API cannot see.
- `VITE_API_BASE_URL` is a build-time frontend contract; Docker build args and CI env must set it explicitly when not using the default.
- CI and Docker Compose start MySQL for migration and Playwright smoke gates.
- Compose API and worker services must not override `DATABASE_URL` after `env_file`;
  otherwise deployment can silently use the internal seed database while operators
  believe `apps/api/.env` points at the real database.
- Slow API requests log `request_slow` when duration exceeds `SLOW_REQUEST_MS`.
- Seed data must not log or print passwords; README may document demo credentials for local-only use.
- Registration creates a pending account, stores only a verification-code hash, and activates the user only after `/auth/verify-email`.
- SMTP delivery failures are recorded on `background_jobs.last_error` and
  `background_job_logs`; logs must not contain passwords or SMTP secrets.
- Password-reset/email-change messages carry raw one-time tokens only in email bodies; DB rows store HMAC hashes and expiry/consumption timestamps.
- Anti-spam rate limits persist sliding-window events in `rate_limit_events`; public errors return generic `rate_limited` or `screening_blocked` without revealing thresholds or screened values.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Empty Docker volume | Migrations and guarded seed run before API serves traffic |
| Existing content database | Guarded seed logs a skip and does not rewrite demo users, boards, topics, or posts |
| API dependency down | Compose healthchecks keep dependent services waiting |
| Frontend built with wrong API URL | README troubleshooting points to `VITE_API_BASE_URL` |
| Slow request | Structured warning log includes method, path, status, duration, threshold |
| Smoke registration conflicts | Test uses unique usernames/boards per run |
| CI lint/type/test failure | Workflow fails before smoke promotion |
| SMTP not configured in real delivery mode | Email job retries then enters dead-letter state; no SMTP secret is logged. |
| Verification code invalid/expired | Account remains pending; login returns `email_not_verified`. |
| Password-reset unknown email | API still returns `200` with the same shape as known emails; no account existence leak. |
| Rate-limited write path | API returns `429 rate_limited`; admin-only `spam_actions` records context. |
| Screened email/IP/URL hit | API returns `403 screening_blocked`; public response does not include matched rule value. |
| Upload volume missing/mismatched | Uploaded metadata may exist but content route returns `upload_not_found`; Compose must mount shared `upload-data`. |
| Backup volume missing/mismatched | Backup metadata may be succeeded but download returns `backup_file_not_found`; Compose must mount shared `backup-data`. |

### 5. Good/Base/Bad Cases

- Good: new developer runs `docker compose up --build`, opens web, sees seeded boards, checks `/metrics`, and can run smoke tests.
- Base: CI runs backend and frontend quality gates, then starts temporary API/web servers and executes Playwright happy path.
- Bad: a Docker entrypoint seeds data before migrations, or CI runs smoke tests against a frontend build pointing at a different API URL.
- Bad: deploying with `EMAIL_DELIVERY_MODE=memory`, which exposes a dev-only verification code in API responses.
- Bad: adding a second standalone worker service instead of a `JOB_HANDLERS` entry in the unified worker.

### 6. Tests Required

- Backend: `ruff check app tests` and `pytest -q`.
- Frontend: `pnpm --dir apps/web lint`, `typecheck`, and `build`.
- Config sanity: `docker compose config`.
- Smoke contract: `pnpm --dir apps/web test:smoke` after API/web are running and Playwright browsers are installed.
- Auth contract: backend tests assert register → pending, login blocked, verify → token, resend rate limit, and `/auth/me` rejects pending users.
- Account security contract: backend tests assert password reset no-enumeration, expiring/one-time reset tokens, email-change tokens, 2FA challenge, and active session revocation.
- Spam prevention contract: backend tests assert registration/topic rate limits, screened email/URL rules, auto-silence, admin screened-rule CRUD, and spam action visibility.

### 7. Wrong vs Correct

#### Wrong

```yaml
command: python -m app.seed && alembic upgrade head && uvicorn app.main:app
```

#### Correct

```yaml
command: sh -c "alembic upgrade head && python -m app.seed --if-empty && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```
