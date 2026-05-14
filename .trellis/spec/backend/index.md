# Backend Development Guidelines

> Backend stack for 平行线（internal package/project name: ParallelLines）: FastAPI, Python 3.12+, SQLAlchemy 2.x async ORM, Alembic, MySQL/PostgreSQL, Redis, and background workers.

## Overview

The backend exposes a REST JSON API under `/api/v1`, generates OpenAPI from FastAPI/Pydantic, and keeps business transactions in service functions rather than routers. The domain model follows a Discourse-inspired split between boards/categories, topics, posts, user read state, actions, notifications, and moderation.

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before creating files.
2. Read `database-guidelines.md` before adding models or queries.
3. Read `error-handling.md` before adding endpoints.
4. Read `quality-guidelines.md` before opening a PR.
5. For cross-layer features, read `../guides/cross-layer-thinking-guide.md`.
