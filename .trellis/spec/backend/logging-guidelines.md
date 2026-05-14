# Backend Logging Guidelines

## Format

Use structured JSON logs in non-local environments. Every request log should include:

- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `user_id` when authenticated
- privacy-preserving client identifier when needed

## Levels

- `DEBUG`: local-only query details and development traces.
- `INFO`: request completion, login success, topic/post creation, moderation actions.
- `WARNING`: rate limits, validation abuse, repeated failed login, suspicious upload.
- `ERROR`: unhandled exceptions, worker failures, notification delivery failures.

## Audit vs Log

Moderation and admin actions must be written to `audit_logs` in addition to application logs. Audit entries are product data and must include actor, action, target, and payload summary.

## Anti-patterns

- Do not log access tokens, refresh tokens, password hashes, or raw private content.
- Do not use print statements in application code.
- Do not swallow worker exceptions without logging and retry/dead-letter handling.
