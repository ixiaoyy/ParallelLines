# Backend Directory Structure

Target root: `apps/api`.

```text
apps/api/
  app/
    main.py                 # FastAPI application factory and middleware
    api/v1/                 # Routers grouped by domain
      auth.py
      boards.py
      topics.py
      posts.py
      notifications.py
      moderation.py
    core/                   # Config, security, logging, rate limits
    db/                     # Async engine/session/base helpers
    models/                 # SQLAlchemy tables; no business logic-heavy methods
    schemas/                # Pydantic request/response models
    services/               # Transactional domain operations
    repositories/           # Reusable query objects and persistence helpers
    workers/                # Background jobs and schedules
    tests/                  # Unit/integration tests mirroring app domains
  alembic/                  # Alembic migrations
  pyproject.toml
```

## Rules

- Routers parse HTTP input, call services, and return Pydantic schemas.
- Services own transactions and cross-aggregate updates. Creating a topic must insert `topics`, first `posts`, update board counters, create read state, and enqueue notifications in one service call.
- Repositories own complex SQL, pagination, and filtering. Do not duplicate query fragments across routers.
- Keep domain names consistent: `Board`, `Topic`, `Post`, `Tag`, `Notification`, `Flag`, `AuditLog`.
- Shared infrastructure belongs in `app/core`, not in feature packages.

## Anti-patterns

- Do not perform database commits from routers.
- Do not return raw ORM objects from API routes.
- Do not add one-off utility modules at the project root.
