from __future__ import annotations

from typing import Any

PUBLIC_API_DESCRIPTION = """
平行线公开 API 契约。

Authentication: endpoints that require a user accept `Authorization: Bearer <access_token>`.
Obtain tokens from `/api/v1/auth/login` or `/api/v1/auth/verify-email`.

Pagination: list endpoints use `limit` plus cursor/query parameters where documented and may return
`meta.next_cursor` in the standard response envelope.

Errors: API errors use `{ "error": { "code", "message", "details" } }`.

Compatibility: `/api/v1` is additive within a minor version. Breaking field removals or semantic
changes require a new version or a documented deprecation window.
""".strip()

PUBLIC_OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "auth", "description": "Registration, login, sessions, and account security."},
    {"name": "boards", "description": "Board/category discovery, settings, members, and topics."},
    {"name": "topics", "description": "Topic detail, replies, lifecycle, polls, and solutions."},
    {"name": "users", "description": "Profiles, directory, private messages, and user privacy."},
    {"name": "admin", "description": "Admin-only operations, backups, settings, and user actions."},
]

COMPATIBILITY_POLICY: dict[str, Any] = {
    "api_version": "v1",
    "stability": "beta",
    "compatible_changes": [
        "adding optional response fields",
        "adding enum values clients must ignore safely",
        "adding endpoints under /api/v1",
    ],
    "breaking_changes": [
        "removing or renaming fields",
        "changing authentication requirements",
        "changing error codes for existing validation paths",
    ],
    "deprecation_window_days": 90,
}

ERROR_EXAMPLE: dict[str, Any] = {
    "error": {
        "code": "validation_error",
        "message": "Request validation failed",
        "details": {"errors": []},
    }
}

AUTH_EXAMPLE: dict[str, str] = {
    "header": "Authorization: Bearer <access_token>",
    "login": "POST /api/v1/auth/login",
    "refresh": "POST /api/v1/auth/refresh",
}

PAGINATION_EXAMPLE: dict[str, Any] = {
    "request": "GET /api/v1/topics?sort=latest&limit=30&cursor=<iso datetime>",
    "response_meta": {"next_cursor": "2026-05-25T12:00:00+00:00"},
}

REQUEST_EXAMPLES: list[dict[str, Any]] = [
    {
        "title": "登录并携带 Bearer Token",
        "request": {
            "method": "POST",
            "path": "/api/v1/auth/login",
            "body": {"account": "alice", "password": "strong-pass-123"},
        },
        "response": {"data": {"access_token": "<jwt>", "token_type": "bearer"}},
    },
    {
        "title": "读取最新主题分页",
        "request": {"method": "GET", "path": "/api/v1/topics?sort=latest&limit=30"},
        "response": {"data": [], "meta": {"next_cursor": None}},
    },
]
