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
| `web` | `pnpm --dir apps/web preview --host 0.0.0.0 --port 5173` | Static Vite preview built with `VITE_API_BASE_URL` |
| `worker` | `python -m app.workers.hot_ranking` | Recomputes topic hot scores every `HOT_RANK_INTERVAL_SECONDS` |
| `db` | `postgres:16-alpine` | PostgreSQL source of truth |
| `redis` | `redis:7-alpine` | Cache/coordination dependency |

API ops endpoints:

- `GET /healthz` returns service health JSON.
- `GET /metrics` returns Prometheus-style text counters:
  - `parallellines_requests_total`
  - `parallellines_request_duration_seconds_total`
  - `parallellines_requests_by_status_total{status="..."}`

Seed command:

- `python -m app.seed` idempotently creates demo users, boards, memberships, and starter topics.

CI commands:

- Backend: `uv sync --frozen`, `uv run ruff check app tests`, `uv run pytest -q`.
- Frontend: `pnpm install --frozen-lockfile`, `pnpm --dir apps/web lint`, `typecheck`, `build`.
- Smoke: `pnpm --dir apps/web test:smoke` against a running API/web pair.

### 3. Contracts

- Docker Compose must start a usable local environment from an empty volume with `docker compose up --build`.
- API startup in Compose must run `alembic upgrade head` before `python -m app.seed`.
- Worker image reuses the API build and must not run migrations.
- `VITE_API_BASE_URL` is a build-time frontend contract; Docker build args and CI env must set it explicitly when not using the default.
- CI uses SQLite for backend tests/smoke to stay self-contained, while Docker Compose uses PostgreSQL.
- Slow API requests log `request_slow` when duration exceeds `SLOW_REQUEST_MS`.
- Seed data must not log or print passwords; README may document demo credentials for local-only use.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Empty Docker volume | Migrations and seed run before API serves traffic |
| API dependency down | Compose healthchecks keep dependent services waiting |
| Frontend built with wrong API URL | README troubleshooting points to `VITE_API_BASE_URL` |
| Slow request | Structured warning log includes method, path, status, duration, threshold |
| Smoke registration conflicts | Test uses unique usernames/boards per run |
| CI lint/type/test failure | Workflow fails before smoke promotion |

### 5. Good/Base/Bad Cases

- Good: new developer runs `docker compose up --build`, opens web, sees seeded boards, checks `/metrics`, and can run smoke tests.
- Base: CI runs backend and frontend quality gates, then starts temporary API/web servers and executes Playwright happy path.
- Bad: a Docker entrypoint seeds data before migrations, or CI runs smoke tests against a frontend build pointing at a different API URL.

### 6. Tests Required

- Backend: `ruff check app tests` and `pytest -q`.
- Frontend: `pnpm --dir apps/web lint`, `typecheck`, and `build`.
- Config sanity: `docker compose config`.
- Smoke contract: `pnpm --dir apps/web test:smoke` after API/web are running and Playwright browsers are installed.

### 7. Wrong vs Correct

#### Wrong

```yaml
command: python -m app.seed && alembic upgrade head && uvicorn app.main:app
```

#### Correct

```yaml
command: sh -c "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```
