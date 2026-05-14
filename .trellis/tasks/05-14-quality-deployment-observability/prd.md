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

- `docker compose up` starts a usable local environment.
- CI fails on lint/type/test regressions.
- Smoke tests cover the MVP happy path.
- README documents setup, development commands, and troubleshooting.
- Basic metrics/logging are available for API and worker.
