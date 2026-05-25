# Backend Database Guidelines

## Stack

- SQLAlchemy async is the database abstraction. Local development currently uses the MySQL connection imported from `D:\work\ai-\.env`; PostgreSQL remains compatible if `DATABASE_URL` uses `postgresql+asyncpg://`.
- SQLAlchemy 2.x async ORM is used for models and queries.
- Alembic is the only migration mechanism.
- Redis is for cache, rate limiting, ephemeral notification fan-out, and background coordination only.

## Core Model Conventions

- Use one primary-key strategy consistently. This project uses database-native `BIGINT`
  auto-increment IDs for primary keys and foreign keys; API response schemas may expose them
  as strings for TypeScript compatibility. Use UUID/ULID only when offline creation,
  cross-region ID generation, or public non-enumerable IDs are a real requirement. If
  sequential IDs must not be exposed, keep internal `BIGINT` IDs and add slugs/public IDs at
  the API boundary instead of making every foreign key a UUID string.
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
- Every business table must have a table comment that explains the table's domain purpose.
- Every business column must have a column comment that explains meaning, ownership, units/status enum, and null semantics when applicable.
- SQLAlchemy models should carry the same comments in metadata so autogenerate/review sees the contract before migrations are written.
- For MySQL migrations, keep Alembic revision IDs short enough for the version table or configure the Alembic version column length before running migrations.
- Minimum indexes:
  - `boards.slug unique`
  - `topics(board_id, last_posted_at desc)`
  - `topics(board_id, hot_score desc)`
  - `posts(topic_id, post_number)` unique
  - `topic_reads(user_id, topic_id)` unique
  - `notifications(user_id, read_at, created_at desc)`

## Schema Comment Contract

### Scope / Trigger

- Applies whenever adding or changing database tables/columns in `app/models/` or `alembic/versions/`.
- Applies to all supported SQL dialects. MySQL must persist comments in `information_schema`; PostgreSQL must use `COMMENT ON`.

### Signatures

- SQLAlchemy table comment: `Table(..., comment="<中文表用途>")` or `__table__.comment = ...`.
- SQLAlchemy column comment: `mapped_column(..., comment="<中文字段含义>")` or `Column(..., comment=...)`.
- Alembic migration must either create the table/column with `comment=` or add a follow-up dialect-aware comment migration.

### Contracts

- Table comment must answer: "这张表保存什么业务对象/关系？"
- Column comment must answer: "字段含义是什么？枚举/计数/时间/为空时代表什么？"
- Shared columns (`id`, `created_at`, `updated_at`, `deleted_at`) may use a centralized comment map, but the resulting database column comment must be non-empty.
- `alembic_version.version_num` must support the longest project revision id; current project sets it to length 128 before migrations run.

### Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| New table migration | Table and every column have comments before PR is ready |
| New column on existing table | Migration adds a column comment in the same change |
| MySQL target | `information_schema.tables.table_comment` and `information_schema.columns.column_comment` are non-empty |
| SQLite target | Comment migration is safe/no-op because SQLite does not persist comments |
| Revision id longer than 32 chars | Alembic version table can still store the revision id |

### Tests Required

- Run backend lint/tests after schema comment changes: `ruff check app tests alembic` and `pytest -q`.
- For MySQL-backed local/dev verification, query `information_schema` and assert zero empty comments for project tables/columns.

### Wrong vs Correct

#### Wrong

```python
name: Mapped[str] = mapped_column(String(80), nullable=False)
```

#### Correct

```python
name: Mapped[str] = mapped_column(String(80), nullable=False, comment="版块名称。")
```

## Anti-patterns

- Do not update counter caches from multiple unrelated places.
- Do not store rendered HTML without also storing raw Markdown.
- Do not use Redis as source of truth.
