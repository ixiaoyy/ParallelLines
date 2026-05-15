# Backend Moderation Admin and Safety Contract

## Scenario: Report queue, content hiding, and audit trails

### 1. Scope / Trigger

- Trigger: implementing community governance across flags, moderator actions, user status changes, and audit logs.
- Applies to `apps/api/app/models/moderation.py`, `schemas/moderation.py`, `services/moderation.py`, `api/v1/moderation.py`, Alembic migrations, and public topic/post visibility code.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/v1/moderation/flags` | active user | Report a `topic` or `post` |
| `GET /api/v1/moderation/queue?status=&limit=` | board moderator/owner or global moderator/admin | List flags scoped to moderatable boards |
| `PUT /api/v1/moderation/flags/{flag_id}/status` | moderator | Move flag to `pending`, `resolved`, or `rejected` |
| `PUT /api/v1/moderation/topics/{topic_id}/hide|restore` | moderator | Soft-hide or restore a topic |
| `PUT /api/v1/moderation/posts/{post_id}/hide|restore` | moderator | Soft-hide or restore a post |
| `PUT /api/v1/moderation/users/{user_id}/status` | admin only | Set `active`, `silenced`, or `suspended` |
| `GET /api/v1/moderation/audit-logs?limit=` | moderator/admin | List audit logs scoped by board permission |

DB tables:

- `flags`: `target_type`, `target_id`, `board_id`, `reporter_id`, `reason`, `detail`, `status`, `resolution_note`, `resolved_by_id`, `resolved_at`, timestamps.
- `audit_logs`: `actor_id`, `action`, `target_type`, `target_id`, `board_id`, `data`, `created_at`.

### 3. Contracts

- A flag target must resolve to an existing non-hidden topic/post when created.
- Flag responses include a `target` snapshot with board, author, topic routing fields, excerpt, and hidden state.
- Moderation permission is granted by:
  - global `User.role in ('admin', 'moderator')`; or
  - `BoardMember.role in ('owner', 'moderator')` for the target board.
- `hide` is a soft delete:
  - topic: set `topics.deleted_at` and `topics.status='hidden'`;
  - post: set `posts.deleted_at`.
- Public topic feeds/search exclude hidden topics via `Topic.deleted_at is null`.
- Public post responses must not leak hidden `raw_md` or `cooked_html`; return empty strings with `deleted_at` set.
- Every flag creation, status transition, hide/restore, and user status change writes an `audit_logs` row in the same transaction.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Unknown target type | `validation_error` / 422 |
| Missing or already-hidden target on flag create | `topic_not_found` or `post_not_found` / 404 |
| Ordinary user reads queue or hides content | `moderation_forbidden` / 403 |
| Board owner/moderator handles own board flag | 200 and audit log written |
| Non-admin changes user status | `admin_required` / 403 |
| Admin attempts to change own status | `cannot_moderate_self` / 422 |
| Hidden topic requested via public topic endpoint | `topic_not_found` / 404 |

### 5. Good/Base/Bad Cases

- Good: reporter creates a flag; board owner sees it in `/moderation/queue`, hides the post, resolves the flag, then sees audit rows.
- Base: admin sets a spammer to `silenced`; the action is captured in `audit_logs` with status transition details.
- Bad: router directly sets `deleted_at` without calling `ModerationService` and therefore skips permission checks or audit logging.

### 6. Tests Required

- `pytest tests/test_moderation.py` must assert:
  - unauthorized users cannot read queue or moderate content;
  - board owners can see scoped flags and hide/restore content;
  - hidden post API payload blanks `raw_md` and `cooked_html`;
  - hidden topics disappear from public reads/lists;
  - non-admin user status updates fail and admin updates succeed;
  - audit log rows are written for moderation actions.
- Full backend regression: `pytest -q` and `ruff check app tests`.

### 7. Wrong vs Correct

#### Wrong

```python
@router.put("/posts/{post_id}/hide")
async def hide_post(post_id: str, session: SessionDep):
    post = await session.get(Post, post_id)
    post.deleted_at = utcnow()
    await session.commit()
```

#### Correct

```python
result = await ModerationService(session).hide_post(post_id, payload, current_user)
return ApiResponse(data=result)
```
