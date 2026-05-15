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
| [Interactions and Notifications](./interactions-notifications.md) | Likes, bookmarks, follows, notification fan-out contracts | Filled |
| [Search, Feed, and Hot Ranking](./search-feed-hot-ranking.md) | Search filters, public feeds, cursor meta, hot score recompute | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Flags, moderation queue, soft hide/restore, user status, audit logs | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | Filled |
| [Deployment and Observability](./deployment-observability.md) | Docker Compose, CI, seed data, metrics, workers, smoke-test contracts | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before creating files.
2. Read `database-guidelines.md` before adding models or queries.
3. Read `error-handling.md` before adding endpoints.
4. Read `interactions-notifications.md` before changing likes, bookmarks, follows, or notifications.
5. Read `search-feed-hot-ranking.md` before changing topic feeds, search, or hot ranking jobs.
6. Read `moderation-admin-safety.md` before changing flags, audit logs, moderator permissions, or hidden content visibility.
7. Read `deployment-observability.md` before changing Docker, CI, seed data, metrics, or worker startup.
8. Read `quality-guidelines.md` before opening a PR.
9. For cross-layer features, read `../guides/cross-layer-thinking-guide.md`.
