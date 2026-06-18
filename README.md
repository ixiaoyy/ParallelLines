# 平行线

面向中文技术社区的 Discourse-inspired 论坛项目，采用 Vue 3 + FastAPI 实现。代码仓库和包名暂沿用 `ParallelLines/parallellines`。

## Stack Target

- Frontend: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query
- Backend: FastAPI, SQLAlchemy 2.x async, Alembic, MySQL, Redis
- Worker: Python async background job runner for notifications, email digests, hot ranking, and cleanup tasks
- Palette: `#F8FAFC`, `#409EFF`, `#10B981`, `#334155`, `#475569`, `#1E1E1E`

## Quick Start with Docker

```powershell
# From repo root
docker compose up -d --build
```

Services:

- Web: <http://localhost> via the Compose Nginx entrypoint
- API: <http://127.0.0.1:8000> for local debugging, and `/api/` via Nginx
- API health: <http://localhost/healthz>
- API metrics: <http://localhost/metrics>
- Redis: `127.0.0.1:6379` for local debugging only

`docker compose up` reads `apps/api/.env`, runs Alembic migrations against the configured
`DATABASE_URL`, builds the frontend with `VITE_API_BASE_URL=/api/v1`, then starts Redis, the
API, the static web Nginx container, the public Nginx entrypoint, and the unified background job
worker. Compose uses only that configured database and does not create users/content automatically.

Production Compose exposes ports 80 and 443 through the Nginx entrypoint. Nginx serves the HTTP-01
challenge from `/opt/parallellines/var/certbot`, persists certificates under
`/opt/parallellines/var/letsencrypt`, and redirects normal HTTP traffic to HTTPS. The deploy
workflow requests a Let's Encrypt certificate for `pingxingxian.space` and `www.pingxingxian.space`
after the containers start; until that succeeds, Nginx starts with a temporary self-signed fallback
certificate so the deployment does not fail before the first certificate is issued.

## Local Development without Docker

### Backend

```powershell
cd apps/api
uv sync
Copy-Item .env.example .env  # then edit DATABASE_URL / JWT_SECRET_KEY
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

For Docker, `apps/api/.env` is the single API configuration file. Set `DATABASE_URL` to the
actual database for the target environment. If the database is remote, keep its remote host in
that file; Compose will not start or override a local MySQL service.

Useful commands:

```powershell
uv run ruff check app tests
uv run pytest -q
uv run python -m app.workers.background_jobs
# Only synchronize the pinned/featured starter posts into the current database; default author is 多动脑子z.
uv run python -m app.sync_quality_posts
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

The frontend reads `VITE_API_BASE_URL`; local dev falls back to `http://127.0.0.1:8000/api/v1`,
while Docker Compose builds the production frontend against the same-origin `/api/v1` path.

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

本地默认使用 `UPLOAD_STORAGE_BACKEND=local`，文件保存到 `UPLOAD_STORAGE_PATH=var/uploads`。
Docker Compose 部署会覆盖容器内路径为 `/var/lib/parallellines/uploads`，并把宿主机目录
`/opt/parallellines/var/uploads` 绑定到该路径，避免镜像重建或命名卷变化导致上传文件不可见。
发帖上传会返回 `/uploads/{id}/content` 引用，创建/编辑帖子后自动绑定到对应楼层。头像通过
`POST /api/v1/uploads/avatar` 更新，并会同步到 `/auth/me` 和公开用户资料。

也可以把新上传切到 S3 兼容存储（例如 Cloudflare R2）。默认前端 URL 和权限检查保持不变，
API 会按每条上传记录的 `storage_backend` 从本地或对象存储读取文件：

```env
UPLOAD_STORAGE_BACKEND=s3
UPLOAD_S3_BUCKET=your-r2-bucket
UPLOAD_S3_REGION=auto
UPLOAD_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
UPLOAD_S3_ACCESS_KEY_ID=your-r2-access-key-id
UPLOAD_S3_SECRET_ACCESS_KEY=your-r2-secret-access-key
UPLOAD_S3_REQUEST_TIMEOUT_SECONDS=10
```

如果 R2 已绑定公开访问域名，可以设置：

```env
UPLOAD_CDN_BASE_URL=https://img.pingxingxian.space
```

这样 API 在完成上传 ACL 校验后，会把图片和缩略图请求 302 到
`https://img.pingxingxian.space/{storage_key}`。如果希望新上传接口直接返回 CDN URL，额外开启：

```env
UPLOAD_PUBLIC_CDN_URLS=true
```

这个开关适合公开图片站点；开启后 Markdown 会保存 `img.pingxingxian.space` 地址，图片 URL
本身就是可直接访问的公开链接。

已有本地文件迁移到 R2 时，保持对象 key 与数据库 `storage_key` 一致，例如
`2026/06/3.png` 和 `_thumbnails/2026/06/3.png.webp`，并把对应上传记录的
`storage_backend` 改为 `s3`；这样旧记录不需要改 URL。

可以用内置迁移脚本分批迁移历史图片。默认只预览 `uploads.storage_backend='local'`
且 `is_image=true` 的记录，不写 R2、不改数据库：

```bash
cd apps/api
uv run python -m app.migrate_uploads_to_s3 --dry-run
```

确认数量和缺失文件后再执行真实迁移：

```bash
uv run python -m app.migrate_uploads_to_s3 --apply
```

脚本会按原 `storage_key` 上传原图，已存在的本地缩略图会迁到
`_thumbnails/{storage_key}.webp`；没有缩略图的图片会在首次请求缩略图时由 API
重新生成到 R2。迁移成功后才把对应上传记录更新为 `storage_backend='s3'`，本地文件
不会被删除。可用 `--limit 100` 先小批量验证，`--start-after-id <id>` 断点续跑，
或用 `--all-files` 把非图片附件也一起迁移。

新上传文件按 UTC 年/月切目录，例如 `2026/05/{upload_id}.jpeg`；旧记录中的历史
`storage_key` 仍按数据库原值读取。

关键限制：

- `UPLOAD_MAX_BYTES`：帖子图片/附件单文件大小。
- `UPLOAD_MAX_AVATAR_BYTES`：头像单文件大小。
- `UPLOAD_MAX_FILES_PER_POST`：单个帖子最多引用的上传数量。
- `UPLOAD_TEMPORARY_TTL_HOURS`：未绑定临时上传的过期时间。
- `BACKGROUND_UPLOAD_CLEANUP_INTERVAL_SECONDS`：统一后台任务 worker 的临时上传清理调度间隔。

### 备份、恢复校验与数据导出

管理员可通过 `/api/v1/admin/backups` 创建站点备份任务，统一后台 worker 会生成包含数据库 JSON 快照和可选上传文件的 ZIP 归档。备份元数据会记录状态、创建人、文件大小和 SHA-256 校验和。

- `BACKUP_STORAGE_PATH`：备份 ZIP 的本地存储目录；Docker Compose 中 API 和 worker 共享 `/opt/parallellines/var/backups` 挂载目录。
- `/api/v1/admin/backups/{id}/download`：仅管理员可下载成功备份，并返回 `X-Backup-SHA256`。
- `/api/v1/admin/backups/{id}/restore`：当前阶段只做非破坏性校验，必须提交 `RESTORE {id}` 确认，生产环境禁用。
- `/api/v1/users/me/export`：登录用户导出自己的资料、主题、帖子和互动记录。
- `/api/v1/admin/exports/site`：管理员导出脱敏后的全站 JSON ZIP。

导出与备份中的 password/token/secret/code 字段会被脱敏，不导出明文密码或一次性令牌。

### 通知邮件、摘要与入站回复

即时通知邮件、每日/每周摘要、退信/投诉回调和入站回复记录都由统一后台任务与 `/api/v1/email/*` API 承载：

- 用户在 `/email-preferences` 管理邮件总开关、单类通知开关和摘要频率。
- `BACKGROUND_DIGEST_INTERVAL_SECONDS` 控制摘要任务调度间隔。
- 配置 `EMAIL_WEBHOOK_SECRET` 后，邮件服务商回调必须传入 `X-Email-Webhook-Secret`。
- 本地可运行 `uv run python -m app.workers.background_jobs` 处理 `mail`、`notifications` 和 `maintenance` 队列。

生产本地存储由 `docker-compose.yml` 固定挂载：

```text
/opt/parallellines/var/uploads  -> /var/lib/parallellines/uploads
/opt/parallellines/var/backups  -> /var/lib/parallellines/backups
```

部署脚本会先创建目录并赋予读写权限；不要执行 `docker compose down -v` 或
`docker system prune --volumes` 清理历史 MySQL 命名卷，除非已确认没有待迁移的旧数据或上传文件。

## Smoke Tests

Playwright smoke tests cover register → login → create board/topic → reply against a running API and web app.

```powershell
# Terminal 1: start API + web, or use docker compose up
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1"
$env:PLAYWRIGHT_API_BASE_URL="http://127.0.0.1/api/v1"
pnpm --dir apps/web exec playwright install chromium
pnpm --dir apps/web test:smoke
```

## CI

`.github/workflows/ci.yml` runs:

1. Backend `uv sync --frozen`, `ruff check`, and `pytest`.
2. Frontend `pnpm install --frozen-lockfile`, lint, typecheck, and build.
3. Playwright MVP smoke tests with a MySQL-backed API and Vite dev server.

## Operations Checklist

Before deployment:

- Set `JWT_SECRET_KEY` to a strong secret; never use the local default.
- Set `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `ENVIRONMENT`, SMTP email settings, `EMAIL_WEBHOOK_SECRET`, background job intervals, upload storage settings, and `BACKUP_STORAGE_PATH` for the target environment.
- Keep host-level Nginx/Apache stopped on ports 80 and 443 when using the Compose Nginx entrypoint.
- Ensure the cloud security group allows inbound TCP 80 and 443 before the first Let's Encrypt request.
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
- Docker API cannot connect to DB: run `docker compose config`, verify `apps/api/.env` has the intended `DATABASE_URL`, then inspect `docker compose logs api worker`.
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
