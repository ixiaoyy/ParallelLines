# 平行线

面向中文技术社区的 Discourse-inspired 论坛项目，采用 Vue 3 + FastAPI 实现。代码仓库和包名暂沿用 `ParallelLines/parallellines`。

## Stack Target

- Frontend: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query
- Backend: FastAPI, SQLAlchemy 2.x async, Alembic, PostgreSQL/MySQL, Redis
- Worker: Python async background job runner for notifications, email digests, hot ranking, and cleanup tasks
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

`docker compose up` runs Alembic migrations, seeds demo data, starts the API, web preview server, PostgreSQL, Redis, and the unified background job worker.

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
uv run python -m app.workers.background_jobs
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

### 注册邮件验证码

本地和 CI 默认使用 `EMAIL_DELIVERY_MODE=memory`，注册接口会返回仅用于开发测试的
`dev_verification_code`，前端会自动填入验证码输入框。真实环境请改为 SMTP：

```powershell
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=noreply@example.com
SMTP_USE_TLS=true
```

生产环境不得使用 `memory` 模式；验证码有效期和重发/尝试限制可通过
`EMAIL_VERIFICATION_CODE_TTL_MINUTES`、`EMAIL_VERIFICATION_RESEND_SECONDS`、
`EMAIL_VERIFICATION_MAX_ATTEMPTS` 调整。

### 上传、头像与附件

本地默认使用 `UPLOAD_STORAGE_BACKEND=local`，文件保存到 `UPLOAD_STORAGE_PATH=var/uploads`，
发帖上传会返回 `/uploads/{id}/content` 引用，创建/编辑帖子后自动绑定到对应楼层。头像通过
`POST /api/v1/uploads/avatar` 更新，并会同步到 `/auth/me` 和公开用户资料。

关键限制：

- `UPLOAD_MAX_BYTES`：帖子图片/附件单文件大小。
- `UPLOAD_MAX_AVATAR_BYTES`：头像单文件大小。
- `UPLOAD_MAX_FILES_PER_POST`：单个帖子最多引用的上传数量。
- `UPLOAD_TEMPORARY_TTL_HOURS`：未绑定临时上传的过期时间。
- `BACKGROUND_UPLOAD_CLEANUP_INTERVAL_SECONDS`：统一后台任务 worker 的临时上传清理调度间隔。

### 通知邮件、摘要与入站回复

即时通知邮件、每日/每周摘要、退信/投诉回调和入站回复记录都由统一后台任务与 `/api/v1/email/*` API 承载：

- 用户在 `/email-preferences` 管理邮件总开关、单类通知开关和摘要频率。
- `BACKGROUND_DIGEST_INTERVAL_SECONDS` 控制摘要任务调度间隔。
- 配置 `EMAIL_WEBHOOK_SECRET` 后，邮件服务商回调必须传入 `X-Email-Webhook-Secret`。
- 本地可运行 `uv run python -m app.workers.background_jobs` 处理 `mail`、`notifications` 和 `maintenance` 队列。

当前已预留 `UPLOAD_CDN_BASE_URL` 和 S3 相关配置项；生产本地存储需把
`UPLOAD_STORAGE_PATH` 挂载到持久化卷。

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
- Set `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `ENVIRONMENT`, SMTP email settings, `EMAIL_WEBHOOK_SECRET`, background job intervals, and upload storage settings for the target environment.
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
