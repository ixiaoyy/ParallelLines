# PRD: Quality Deployment Observability

## Goal

Make the project easy to run, test, deploy, and operate.

## Scope

- Docker Compose for web, api, database, redis, worker.
- Seed data for boards/topics/posts/users.
- CI with backend lint/test and frontend lint/typecheck/test.
- Playwright smoke tests for register/login/create-topic/reply.
- Structured logging, request IDs, slow query logging.
- Deployment and rollback checklist.

## Acceptance Criteria

- [x] `docker compose up` starts a usable local environment.
- [x] CI fails on lint/type/test regressions.
- [x] Smoke tests cover the MVP happy path.
- [x] README documents setup, development commands, and troubleshooting.
- [x] Basic metrics/logging are available for API and worker.

## Progress

- [x] Added `docker-compose.yml`, API Dockerfile, web Dockerfile, and Docker ignore files.
- [x] Added idempotent backend seed command with demo users, boards, memberships, and topics.
- [x] Added API `/metrics`, slow request logging threshold, and worker hot-ranking runtime loop.
- [x] Added GitHub Actions CI for backend, frontend, and Playwright smoke path.
- [x] Added Playwright smoke spec covering register/login via API plus frontend create-topic/reply flow.
- [x] Expanded README operations, setup, smoke, CI, troubleshooting, and rollback docs.
- [x] Updated code-specs for deployment/observability and smoke test contracts.
