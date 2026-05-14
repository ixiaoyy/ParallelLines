# Backend Error Handling

## Response Shape

All API errors must use this shape:

```json
{
  "error": {
    "code": "topic_not_found",
    "message": "Topic not found",
    "details": {}
  }
}
```

## Exception Types

- `AppError`: base typed error with `code`, `message`, `status_code`, and `details`.
- `NotFoundError`: missing board/topic/post/user.
- `PermissionDeniedError`: authenticated user lacks permission.
- `ValidationError`: domain validation beyond Pydantic field checks.
- `RateLimitError`: posting/search/action throttles.
- `ConflictError`: duplicate slug, duplicate reaction, stale update.

## Rules

- Convert all domain exceptions to HTTP responses in global exception handlers.
- Pydantic request validation should be normalized to the project error shape if practical.
- Log server errors with `request_id`; do not log passwords, tokens, raw cookies, or full private message bodies.
- Services should raise domain errors; routers should not manually build many `HTTPException`s.

## Anti-patterns

- Do not leak stack traces or database constraint names to clients.
- Do not return localized strings as stable error codes.
- Do not treat authorization failures as missing data unless it is an intentional privacy decision.
