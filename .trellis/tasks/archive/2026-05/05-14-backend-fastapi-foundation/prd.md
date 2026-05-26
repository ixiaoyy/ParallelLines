# PRD: Backend FastAPI Foundation

## Goal

Create the backend skeleton and infrastructure needed by the ParallelLines MVP.

## Scope

- FastAPI app factory, `/healthz`, `/api/v1` router.
- Config management, structured logging, request ID middleware.
- Async SQLAlchemy session, Alembic migrations, MySQL setup.
- Redis client and rate limit adapter.
- Auth foundation: register, login, refresh, logout, current user.
- Base Pydantic schemas, error handlers, test setup.

## Acceptance Criteria

- App starts locally and exposes OpenAPI.
- Clean database can run all Alembic migrations.
- Auth happy path has tests.
- Global error response shape matches `.trellis/spec/backend/error-handling.md`.
- No business logic lives in routers beyond request orchestration.
