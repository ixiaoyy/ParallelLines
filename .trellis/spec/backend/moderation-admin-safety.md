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
| `PUT /api/v1/topics/{topic_id}/lifecycle` | moderator | Close/open/archive or pin/unpin a topic |
| `POST /api/v1/topics/{topic_id}/move|split|merge` | moderator | Move a topic, split replies into a new topic, or merge a source topic into a target |
| `PUT /api/v1/moderation/users/{user_id}/status` | admin only | Set `active`, `silenced`, or `suspended` |
| `GET /api/v1/moderation/audit-logs?limit=` | moderator/admin | List audit logs scoped by board permission |
| `GET /api/v1/moderation/screened-rules?kind=&limit=` | admin only | List anti-spam email/IP/URL screening rules |
| `POST /api/v1/moderation/screened-rules` | admin only | Create a screening rule |
| `DELETE /api/v1/moderation/screened-rules/{rule_id}` | admin only | Remove a screening rule |
| `GET /api/v1/moderation/spam-actions?limit=` | admin only | List automatic anti-spam actions |

DB tables:

- `flags`: `target_type`, `target_id`, `board_id`, `reporter_id`, `reason`, `detail`, `status`, `resolution_note`, `resolved_by_id`, `resolved_at`, timestamps.
- `audit_logs`: `actor_id`, `action`, `target_type`, `target_id`, `board_id`, `data`, `created_at`.
- `topics.merged_into_topic_id`: nullable pointer to the target topic after a merge.
- `users`: `role` (`user`, `moderator`, `admin`) and `level` (`int`, default `0`).

Permission helpers:

- `app.core.permissions.is_admin(user)`
- `app.core.permissions.is_global_moderator(user)`
- `app.core.permissions.BOARD_MODERATOR_ROLES`

### 3. Contracts

- A flag target must resolve to an existing non-hidden topic/post when created.
- Duplicate pending flags for the same `target_type` + `target_id` + `reporter_id` are idempotent:
  return the existing flag response and do not insert another `flags` or `audit_logs` row.
- Flag responses include a `target` snapshot with board, author, topic routing fields, excerpt, and hidden state.
- Moderation permission is granted by:
  - global `User.role in ('admin', 'moderator')`; or
  - `BoardMember.role in ('owner', 'moderator')` for the target board.
- User status changes are admin-only and must call `is_admin(current_user)` rather than direct string comparisons in services.
- User `level` is not an authorization field. It defaults to `0` and may be displayed or used by growth features, but role remains the permission source of truth.
- `hide` is a soft delete:
  - topic: set `topics.deleted_at` and `topics.status='hidden'`;
  - post: set `posts.deleted_at`.
- Public topic feeds/search exclude hidden topics via `Topic.deleted_at is null`.
- Public post responses must not leak hidden `raw_md` or `cooked_html`; return empty strings with `deleted_at` set.
- Every flag creation, status transition, hide/restore, and user status change writes an `audit_logs` row in the same transaction.
- Screened-rule create/delete is global admin-only and writes `screened_rule_created` /
  `screened_rule_deleted` audit logs; details are admin-only and must not leak in public
  screening errors.
- Post edits and moderator restores write `post_edited` / `post_revision_restored`
  audit logs; revision bodies stay behind post-revision permissions and are not included
  in public post responses.
- Topic lifecycle actions are moderation actions and must share the same permission contract:
  `topic_status_changed`, `topic_pinned_changed`, `topic_moved`, `topic_split`, and
  `topic_merged` audit rows are written with source/target board/topic IDs and moved post
  counts. See `topic-lifecycle.md` for counter, notification, upload, revision, and
  merged-topic redirect details.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Unknown target type | `validation_error` / 422 |
| Missing or already-hidden target on flag create | `topic_not_found` or `post_not_found` / 404 |
| Same reporter repeats a pending report on the same target | 201 with the existing `FlagResponse.id`; queue count unchanged |
| Ordinary user reads queue or hides content | `moderation_forbidden` / 403 |
| Board owner/moderator handles own board flag | 200 and audit log written |
| Non-admin changes user status | `admin_required` / 403 |
| New registered user | `role='user'`, `level=0`, and no admin-only access |
| Existing user after level migration | `level=0` and existing `role` preserved |
| Admin attempts to change own status | `cannot_moderate_self` / 422 |
| Hidden topic requested via public topic endpoint | `topic_not_found` / 404 |
| Moderator merges a topic | Source topic is hidden, `merged_into_topic_id` is set, and `topic_merged` audit row is written |
| Public read of merged source topic with target access | `topic_merged` / 409 with `target_topic_id` |

### 5. Good/Base/Bad Cases

- Good: reporter creates a flag; board owner sees it in `/moderation/queue`, hides the post, resolves the flag, then sees audit rows.
- Base: admin sets a spammer to `silenced`; the action is captured in `audit_logs` with status transition details.
- Bad: router directly sets `deleted_at` without calling `ModerationService` and therefore skips permission checks or audit logging.
- Bad: topic move/split/merge updates posts but skips `audit_logs`, board counters, or related notification/upload/revision rows.
- Bad: `if user.level > 0:` grants moderation/admin powers; levels are not permissions.

### 6. Tests Required

- `pytest tests/test_moderation.py` must assert:
  - unauthorized users cannot read queue or moderate content;
  - board owners can see scoped flags and hide/restore content;
  - hidden post API payload blanks `raw_md` and `cooked_html`;
  - hidden topics disappear from public reads/lists;
  - non-admin user status updates fail and admin updates succeed;
  - audit log rows are written for moderation actions.
- `pytest tests/test_topic_lifecycle.py` must assert lifecycle audit actions, moderator-only access, hidden merged sources, and board/topic counter maintenance.
- Auth/profile tests must assert registered users default to `role='user'` and `level=0`, and profile/current-user DTOs include `level`.
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

## Scenario: Content safety filtering for topic/post writes

### 1. Scope / Trigger

- Trigger: adding or changing pre-publication content safety filters for topic title/body, replies, or post edits.
- Applies to `apps/api/app/services/content_safety.py` and the write paths in `ForumService.create_topic`, `ForumService.reply_to_topic`, and `ForumService.update_post`.

### 2. Signatures

Service functions:

| Function | Purpose |
|---|---|
| `moderate_text_fields(fields: Mapping[str, str]) -> ContentModerationResult` | Normalize fields, detect configured rules, and return sanitized text plus matched field lists |
| `enforce_content_policy(fields: Mapping[str, str]) -> dict[str, str]` | Apply rules and raise `ValidationError("content_policy_violation")` when a blocking rule matches |

Initial rule actions:

- `block`: reject the write with `content_policy_violation`.
- `mask`: replace matched text spans with `***` before Markdown rendering/storage.
- Pending-review/auto-hide remains a future action until a persisted review state is added.

### 3. Contracts

- Filter coverage:
  - topic creation checks `title` and `raw_md`;
  - reply creation checks `raw_md`;
  - first-post edit checks `raw_md` before rendering.
- Normalization must run `NFKC` + `casefold()` and ignore control, punctuation, symbol, and separator characters so full-width letters, casing, spaces, and punctuation cannot trivially bypass policy.
- Blocking errors must not include the matched token or full rule list. Details may include only `{"action": "blocked", "fields": [...]}`.
- Masking happens before `render_markdown`, so `raw_md` and `cooked_html` both store/render the masked value.
- Public search over post bodies must exclude `Post.deleted_at is not null`; hidden post text must not make a visible topic discoverable by query.
- Public placeholder tokens in tests are allowed; real policy terms must be delivered through a private deployment channel before production use.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Topic title hits a blocking rule after normalization | `content_policy_violation` / 422 with `fields=["title"]` |
| Reply body uses full-width/case/punctuation/space bypass | `content_policy_violation` / 422 with `fields=["raw_md"]` |
| First-post edit hits a blocking rule | `content_policy_violation` / 422 and original post remains unchanged |
| Body hits a mask rule | 201/200; stored `raw_md` and `cooked_html` contain `***` and not the token |
| Hidden post body matches a search query | Search/feed do not return the topic because the matching hidden post is excluded |

### 5. Good/Base/Bad Cases

- Good: `ForumService.create_topic` calls `enforce_content_policy({"title": ..., "raw_md": ...})`, stores sanitized fields, then renders Markdown.
- Base: A mask-only rule replaces a configured local placeholder token with `***` while allowing the post to publish.
- Bad: A router performs ad-hoc string matching or returns the matched policy token in API error details.
- Bad: Search `post_match` scans hidden posts and leaks moderated text through topic discovery.

### 6. Tests Required

- `tests/test_content_safety.py` must assert:
  - block rules reject topic titles, replies, and edits;
  - normalization catches full-width, casing, punctuation, and spaces;
  - blocking responses do not leak the configured token;
  - mask rules store/render `***`;
  - hidden post text does not affect public search results.
- Full backend regression: `ruff check app tests alembic` and `pytest -q --tb=short`.

### 7. Wrong vs Correct

#### Wrong

```python
if "secret-token" in payload.raw_md:
    raise ValidationError("content_policy_violation", "Matched secret-token")
```

#### Correct

```python
filtered = enforce_content_policy({"raw_md": payload.raw_md})
raw_md = filtered["raw_md"].strip()
post.cooked_html = self._render_required_markdown(raw_md)
```
