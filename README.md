# 平行线

面向中文技术社区的 Discourse-inspired 论坛项目，采用 Vue 3 + FastAPI 实现。代码仓库和包名暂沿用 `ParallelLines/parallellines`。

## Stack Target

- Frontend: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query
- Backend: FastAPI, SQLAlchemy 2.x async, Alembic, PostgreSQL/MySQL, Redis
- Worker: Python async background jobs for hot ranking and future notifications/search indexing
- Palette: `#F8F9FA`, `#3B82F6`, `#10B981`, `#111827`, `#4B5563`, `#1E1E1E`

## Quick Start with Docker

```powershell
# From repo root
docker compose up --build
```

Services:

- Web: <http://localhost:5174>
- API: <http://localhost:8000>
- API health: <http://localhost:8000/healthz>
- API metrics: <http://localhost:8000/metrics>
- PostgreSQL: `localhost:5432`, database/user/password `parallellines/postgres/postgres`
- Redis: `localhost:6379`

`docker compose up` runs Alembic migrations, seeds demo data, starts the API, web preview server, PostgreSQL, Redis, and the hot-ranking worker.

Demo accounts share this local-only password: `parallellines-demo-123`.

| Username | Role |
|---|---|
| `demo_admin` | admin |
| `demo_moderator` | moderator |
| `demo_member` | user |

## Local Development without Docker

### Backend

```powershell
cd apps/api
uv sync
Copy-Item .env.example .env  # then edit DATABASE_URL / JWT_SECRET_KEY
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

Useful commands:

```powershell
uv run ruff check app tests
uv run pytest -q
uv run python -m app.workers.hot_ranking
```

### Frontend

```powershell
pnpm install
pnpm --dir apps/web dev
```

Useful commands:

```powershell
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```

The frontend reads `VITE_API_BASE_URL`; the default is `http://localhost:8000/api/v1`.

## Smoke Tests

Playwright smoke tests cover register → login → create board/topic → reply against a running API and web app.

```powershell
# Terminal 1: start API + web, or use docker compose up
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:5174"
$env:PLAYWRIGHT_API_BASE_URL="http://127.0.0.1:8000/api/v1"
pnpm --dir apps/web exec playwright install chromium
pnpm --dir apps/web test:smoke
```

## CI

`.github/workflows/ci.yml` runs:

1. Backend `uv sync --frozen`, `ruff check`, and `pytest`.
2. Frontend `pnpm install --frozen-lockfile`, lint, typecheck, and build.
3. Playwright MVP smoke tests with a SQLite-backed API and Vite dev server.

## Operations Checklist

Before deployment:

- Set `JWT_SECRET_KEY` to a strong secret; never use the local default.
- Set `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, and `ENVIRONMENT` for the target environment.
- Run `alembic upgrade head` before starting new application code.
- Check `/healthz`, `/metrics`, API request logs, and worker logs after rollout.
- Run smoke tests against the target environment or staging before promotion.

Rollback:

1. Stop workers first to prevent background writes during rollback.
2. Roll back application containers to the previous image.
3. If a migration is incompatible, run the matching Alembic downgrade only after backing up data.
4. Re-run smoke tests and verify `/metrics` request counters move after traffic resumes.

Troubleshooting:

- API returns 401 after login: verify `JWT_SECRET_KEY` is stable across API replicas.
- Frontend cannot call API: verify `VITE_API_BASE_URL` was set at build time and `CORS_ORIGINS` includes the web origin.
- Docker API cannot connect to DB: wait for `db` healthcheck or inspect `docker compose logs db api`.
- Smoke test cannot find new board: confirm the API URL points to the same backend used by the web app.

## Design Artifacts

- Product/architecture design: `.trellis/spec/product/discourse-inspired-parallellines-design.md`
- Trellis task plan: `.trellis/spec/product/trellis-task-plan.md`
- Trellis task tree: `.trellis/tasks/05-14-parallellines-mvp`

## Trellis

```powershell
python .trellis\scripts\get_context.py
python .trellis\scripts\task.py list
python .trellis\scripts\task.py start 05-14-parallellines-mvp
```
