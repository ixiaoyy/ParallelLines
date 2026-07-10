# Import, Export, and Migration Tools Backend Contract

## Scope / Trigger

Applies when changing admin JSON migration import preview/run/export APIs.

## Signatures

- `POST /api/v1/admin/migrations/import/preview` validates and dry-runs JSON import.
- `POST /api/v1/admin/migrations/import/run` imports users, boards, topics, posts, and tags idempotently.
- `GET /api/v1/admin/migrations/export` returns a redacted JSON migration snapshot.

## Import Format

`MigrationImportRequest` supports `users`, `boards`, `topics`, and `posts` arrays. User records may
set `is_persona` (default `false`) so imported persona publishers stay out of real-user growth.
Topics resolve by `(board_slug, slug)` and optional `external_id`; posts resolve by
`topic_external_id` during the same run or by `(board_slug, topic_slug)`.

## Contracts

- All migration APIs require admin role.
- Preview must not persist data; it uses the same service path and rolls back.
- Run is idempotent: existing usernames/emails, board slugs, topic slugs, and post numbers are skipped.
- Importing `is_persona=true` may promote an existing matching user to persona; an omitted or false
  value must never silently unmark an existing persona. Export preserves the flag for round trips.
- Errors are reported per row and do not prevent other valid rows from being processed.
- Export omits password hashes, tokens, secrets, and private-message/private-board content in this phase.

## Validation Matrix

| Case | Expected |
|---|---|
| Preview valid sample | Created/skipped/error counts returned; DB unchanged. |
| Second run same payload | Duplicate rows skipped. |
| Missing board/user | Row-level error with no exception leak. |
| Export | JSON contains users/boards/topics/posts/tags and no secret fields. |
| Persona user round trip | `is_persona=true` survives import and export; ordinary users default false. |

## Tests

Downgraded roadmap scope: `pytest tests/test_import_export_migrations.py -q` plus focused ruff.
