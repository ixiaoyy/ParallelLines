# Backend Post Revisions and Restore Contract

## Scenario: Post edit history, version detail, and moderator restore

### 1. Scope / Trigger

- Trigger: changing post edit, revision history, revision restore, or audit behavior.
- Applies to `apps/api/app/models/forum.py`, `schemas/forum.py`, `services/forum.py`, `api/v1/posts.py`, Alembic migrations, and search/feed reads that depend on `posts.raw_md`.

### 2. Signatures

API endpoints:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `PATCH` | `/api/v1/posts/{post_id}` | author or moderator | Update first-post Markdown and optionally pass `edit_reason`. |
| `GET` | `/api/v1/posts/{post_id}/revisions` | author or moderator | List saved previous versions, newest first. |
| `GET` | `/api/v1/posts/{post_id}/revisions/{revision_id}` | author or moderator | Read one saved previous version. |
| `POST` | `/api/v1/posts/{post_id}/revisions/{revision_id}/restore` | moderator only | Restore a saved version to the live post. |

DB table:

- `post_revisions`: `post_id`, `topic_id`, `editor_id`, `version_number`, `raw_md`, `cooked_html`, `edit_reason`, `summary`, `restored_from_revision_id`, `created_at`.

Audit actions:

- `post_edited`
- `post_revision_restored`

### 3. Contracts

- Each successful `PATCH /posts/{post_id}` must save the pre-edit `raw_md` and `cooked_html` to `post_revisions` before overwriting the live post.
- `PostUpdateRequest` accepts `{ raw_md, edit_reason? }`; blank/omitted reasons are stored as `null`, and `summary` is auto-generated from reason or content length delta.
- `version_number` is monotonically increasing per `post_id`; `(post_id, version_number)` is unique.
- Revision reads are allowed for:
  - the post author when the post/topic is not hidden/deleted;
  - global moderator/admin;
  - board owner or board moderator.
- Hidden/deleted post or topic revision history is visible only to moderators; ordinary authors receive `post_not_found`.
- Restore is moderator-only. It must:
  - create a new revision containing the pre-restore live content;
  - set `restored_from_revision_id` to the restored revision;
  - copy the restored revision's `raw_md` and `cooked_html` back to the live post;
  - write `post_revision_restored` audit log in the same transaction.
- Public topic/post views still return only live `posts.raw_md`/`cooked_html`; revision bodies are never included in public topic responses.
- Search remains consistent because it searches live `posts.raw_md`, not `post_revisions.raw_md`.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Empty edited Markdown after trim | `empty_post` / 422 |
| Stranger lists another user's revisions | `permission_denied` / 403 |
| Author lists hidden/deleted post revisions | `post_not_found` / 404 |
| Board owner lists hidden post revisions | 200 |
| Author attempts restore | `moderation_forbidden` / 403 |
| Unknown revision for the post | `post_revision_not_found` / 404 |
| Restore succeeds | live post content equals selected revision and a new revision stores previous live content |

### 5. Good/Base/Bad Cases

- Good: author edits first post with `edit_reason`; API returns updated post, history contains old Markdown and audit has `post_edited`.
- Base: board owner restores revision 1; history gains revision 2 with pre-restore content and `restored_from_revision_id=revision1`.
- Bad: directly overwriting `Post.raw_md` without calling `_create_post_revision`, which loses auditability.
- Bad: public `GET /topics/{id}/posts` includes revision bodies or hidden post revision text.

### 6. Tests Required

- `tests/test_post_revisions.py` must assert:
  - author can list/detail versions after editing;
  - stranger cannot read history;
  - hidden history is moderator-only;
  - author cannot restore and board owner/moderator can restore;
  - restore updates live search results and writes audit logs.
- Regression tests: `ruff check app tests alembic`, `pytest -q --tb=short`, and clean Alembic upgrade through the latest revision.

### 7. Wrong vs Correct

#### Wrong

```python
post.raw_md = payload.raw_md.strip()
post.cooked_html = render_markdown(post.raw_md)
```

#### Correct

```python
revision = await self._create_post_revision(
    post,
    editor=current_user,
    reason=payload.edit_reason,
    next_raw_md=stripped,
)
post.raw_md = stripped
self._add_audit_log(action="post_edited", target_type="post", target_id=post.id, ...)
```
