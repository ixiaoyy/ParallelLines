# Backend Quality Guidelines

## Required Checks

- `ruff check` and formatter checks.
- `mypy` or pyright for typed modules when configured.
- `pytest` for unit and integration tests.
- Alembic migration upgrade on a clean database.

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
