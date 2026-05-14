# Backend Database Guidelines

## Stack

- SQLAlchemy async is the database abstraction. Local development currently uses the MySQL connection imported from `D:\work\ai-\.env`; PostgreSQL remains compatible if `DATABASE_URL` uses `postgresql+asyncpg://`.
- SQLAlchemy 2.x async ORM is used for models and queries.
- Alembic is the only migration mechanism.
- Redis is for cache, rate limiting, ephemeral notification fan-out, and background coordination only.

## Core Model Conventions

- Use UUID or big integer primary keys consistently; choose one during the backend foundation task and document it in the first migration.
- Tables use plural snake_case names: `boards`, `topics`, `posts`, `topic_reads`.
- Timestamps: `created_at`, `updated_at`; soft deletable rows also have `deleted_at` and optionally `deleted_by_id`.
- Slugs are stored separately from titles/names and must be unique within their natural scope.
- Counter caches are allowed for hot paths: `boards.topic_count`, `topics.reply_count`, `topics.hot_score`. Update them in services/jobs only.

## Query Patterns

- Use cursor pagination for public feeds and long post streams.
- Use explicit `selectinload`/joined loading for known relationships; avoid accidental N+1.
- Start search with database-native full-text search where practical; leave an adapter seam for Meilisearch/OpenSearch later.
- Keep hot ranking calculations deterministic and testable.

## Migration Rules

- Every schema change requires an Alembic migration and a test or seed update when relevant.
- Data migrations must be idempotent and safe to rerun in development.
- Minimum indexes:
  - `boards.slug unique`
  - `topics(board_id, last_posted_at desc)`
  - `topics(board_id, hot_score desc)`
  - `posts(topic_id, post_number)` unique
  - `topic_reads(user_id, topic_id)` unique
  - `notifications(user_id, read_at, created_at desc)`

## Anti-patterns

- Do not update counter caches from multiple unrelated places.
- Do not store rendered HTML without also storing raw Markdown.
- Do not use Redis as source of truth.
