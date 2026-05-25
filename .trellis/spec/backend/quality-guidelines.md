# Backend Quality Guidelines

## Required Checks

- `ruff check` and formatter checks.
- `mypy` or pyright for typed modules when configured.
- `pytest` for unit and integration tests.
- Alembic migration upgrade on a clean database.

## Default Roadmap Testing Scope

- During normal development of roadmap tasks, default to downgraded testing: run backend lint and
  one focused pytest smoke/regression target for the touched behavior.
- Do not add or run broad per-task backend matrices by default; final product-level verification
  will cover the full integrated behavior after larger changes settle.
- Escalate to detailed backend tests only when the user explicitly requests detailed/full testing,
  when preparing a commit/release, or when the change is high-risk (schema/data migration, security,
  permissions, irreversible data mutation).

## Test Expectations

- Routers: authentication, permissions, validation, response shape.
- Services: transactional behavior and counter cache updates.
- Repositories: filters, pagination, ordering, no duplicate rows.
- Security: Markdown sanitization, upload validation, rate limit paths.

## Coding Rules

- Use type hints on public functions and service methods.
- Keep router functions thin and readable.
- Prefer explicit dependency injection for current user, DB session, and settings.
- Keep background jobs idempotent.

## Anti-patterns

- No broad `except Exception` unless it re-raises or converts to a typed error after logging.
- No hidden network calls in request path without timeout.
- No direct SQL string concatenation with user input.
