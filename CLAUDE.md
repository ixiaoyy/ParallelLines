# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**平行线** (ParallelLines) - A Discourse-inspired forum for Chinese tech communities.
Stack: Vue 3 + FastAPI (monorepo: `apps/api` + `apps/web`)

- Frontend: Vue 3, Vite, TypeScript, Ant Design Vue, Pinia, TanStack Query
- Backend: FastAPI, SQLAlchemy 2.x async, MySQL, Redis
- Worker: Python async background jobs (notifications, emails, hot ranking)

## Common Commands

```powershell
# Docker (full stack)
docker compose up --build

# Backend (local)
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Frontend (local)
cd apps/web
pnpm install
pnpm dev

# Lint & Typecheck
uv run ruff check app tests                          # Backend
pnpm --dir apps/web lint                             # Frontend
pnpm --dir apps/web typecheck                        # Frontend

# Tests (see Testing Rules below)
uv run pytest -q                                    # Backend (requires DB)
pnpm test:smoke                                     # Playwright smoke tests

# Background worker
uv run python -m app.workers.background_jobs

# Sync quality posts
uv run python -m app.sync_quality_posts
```

## Architecture

### Backend (`apps/api/app/`)

```
api/v1/           # Routers: auth, boards, topics, posts, notifications, moderation, admin, users, etc.
core/             # Config, security, logging, rate limits
db/               # Async engine/session/base helpers
models/           # SQLAlchemy tables (no business logic)
schemas/          # Pydantic request/response models
services/         # Transactional domain operations
repositories/     # Reusable query objects
workers/          # Background jobs and schedules
```

**Layer Rules:**
- Routers: parse HTTP, call services, return Pydantic schemas
- Services: own transactions, cross-aggregate updates (e.g., create topic → insert topic + first post + update counters + enqueue notifications)
- Repositories: complex SQL, pagination, filtering

### Frontend (`apps/web/src/`)

```
features/         # Domain modules: auth, boards, topics, posts, users, moderation, etc.
shared/           # api/, ui/, lib/, router/, styles/, i18n/, theme/
entities/         # Shared type definitions
pages/            # Route pages
```

**State Management:**
- Server state → TanStack Query
- Global client state → Pinia (auth, UI preferences)
- URL state → Vue Router query params
- Local UI state → component refs

## Testing Rules

- **Do NOT run `pnpm test:api` by default** - local test DB isn't configured by default (MySQL connection will fail)
- Lightweight validation: `git diff --check`, `python -m py_compile ...`
- Run `pnpm typecheck:web` for frontend changes
- Only run `pnpm test:api` when user explicitly requests or confirms test DB is ready

## Error Handling (Backend)

All API errors follow this shape:
```json
{ "error": { "code": "topic_not_found", "message": "...", "details": {} } }
```

Exception types: `AppError`, `NotFoundError`, `PermissionDeniedError`, `ValidationError`, `RateLimitError`, `ConflictError`

## Frontend Type Safety

- Use generated OpenAPI types for API DTOs (`TopicResponse`, `CreateTopicRequest`)
- Define UI-only types in owning feature module (`TopicCardVM`, `PostItemVM`)
- Discriminated unions for notification types, moderation states, topic status
- No `any` except at documented integration boundaries

## Design Guidelines

See `AGENTS.md` for detailed frontend styling rules:
- Primary color: `#409EFF` (Element UI classic blue)
- Main buttons: solid `#409EFF` + white text via CSS variables (`--btn-primary-*`)
- Board tones via `boardPalette.ts` (1-6 color schemes for different boards)
- Brand gradient (`--gradient-brand`) is decoration only, NOT for buttons

## Trellis Project Management

```powershell
python .trellis\scripts\get_context.py
python .trellis\scripts\task.py list
python .trellis\scripts\task.py start <task-id>
```

## Service URLs (Docker)

- Web: http://localhost:5174
- API: http://localhost:8000
- API health: http://localhost:8000/healthz