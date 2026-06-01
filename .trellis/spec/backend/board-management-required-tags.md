# Backend Board Management, Required Tags, and Defaults Contract

## Scenario: Board hierarchy, scoped moderators, required tags, templates, and default policies

### 1. Scope / Trigger

- Trigger: changing board settings, child-board hierarchy, board member roles, required/allowed tags, topic templates, board default notification level, or board default sort.
- Applies to `app/models/forum.py`, `schemas/forum.py`, `services/forum.py`, `api/v1/boards.py`, Alembic migrations, schema comments, topic creation, board notifications, and board management tests.

### 2. Signatures

Database fields on `boards`:

- `parent_board_id -> boards.id`, nullable, `ON DELETE SET NULL`.
- `required_tags: JSON | null`: normalized tag names that every new topic in this board must include.
- `allowed_tags: JSON | null`: normalized tag names allowed for new topics; empty/null means unrestricted.
- `post_template: TEXT | null`: Markdown template suggested by the new-topic UI.
- `default_notification_level: "muted" | "normal" | "tracking" | "watching"`.
- `default_sort: "latest" | "hot" | "top"`.

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/api/v1/boards/{slug}/settings` | board owner/admin | Read editable board settings and members |
| `PUT` | `/api/v1/boards/{slug}/settings` | board owner/admin | Update hierarchy, tags, template, defaults |
| `PUT` | `/api/v1/boards/{slug}/members/{username}` | board owner/admin | Create/update a board member role |
| `DELETE` | `/api/v1/boards/{slug}/members/{username}` | board owner/admin | Remove a non-owner board member |

Request payloads:

```python
class BoardSettingsUpdateRequest(BaseModel):
    parent_board_id: str | None = None
    parent_board_slug: str | None = None
    required_tags: list[str] = []
    allowed_tags: list[str] = []
    post_template: str | None = None
    default_notification_level: NotificationLevel = "normal"
    default_sort: Literal["latest", "hot", "top"] = "latest"

class BoardMemberUpdateRequest(BaseModel):
    role: Literal["follower", "moderator"]
    notification_level: NotificationLevel | None = None
```

### 3. Contracts

- Board settings are managed only by the board owner or global admin.
- Board moderators are scoped by `BoardMember(board_id, user_id, role="moderator")`; they may moderate only topics in that board unless they also have global moderator/admin role.
- `BoardResponse` and `BoardDetailResponse` must expose hierarchy/default/tag/template fields needed by the frontend.
- `BoardDetailResponse.child_boards` contains visible direct children only; list endpoints still rely on server-side visibility filtering.
- Board list/detail/topic-list responses may use short-lived hot caches for
  loading speed, but cache keys must include the visibility scope (`anonymous`
  or authenticated user id) and all route filters. Cached board data must never
  expose private boards, membership state, or follow state across users.
- Topic creation validates board policy before creating tags/posts:
  - missing any `required_tags` raises `required_tags_missing`;
  - using a tag outside non-empty `allowed_tags` raises `tag_not_allowed`;
  - required tags must be a subset of allowed tags when allowed tags are configured.
- Board member creation increments `follower_count` only when inserting a new `BoardMember`.
- Removing a member decrements `follower_count`, but owner membership cannot be removed/demoted through member routes.
- New invite acceptances and board follows default to `board.default_notification_level` when no explicit level is supplied.
- Board parent changes must reject self-parenting and cycles.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Non-owner/non-admin updates board settings | `board_settings_forbidden` / 403 |
| Parent board does not exist or is not visible to manager | `board_not_found` / 404 |
| Parent board is the same board | `board_parent_invalid` / 422 |
| Parent update creates a cycle | `board_parent_cycle` / 422 |
| Required tag is outside allowed tag list | `required_tags_not_allowed` / 422 |
| Topic missing required tags | `required_tags_missing` / 422 with `missing_tags` |
| Topic includes disallowed tag | `tag_not_allowed` / 422 with `disallowed_tags` |
| Owner attempts to remove/demote owner membership | `board_owner_role_protected` / 422 |
| Board moderator closes topic in own board | 200 |
| Same board moderator closes topic in another board | `moderation_forbidden` / 403 |

### 5. Good/Base/Bad Cases

- Good: Owner configures `required_tags=["bug"]`; a topic without `bug` fails before tag rows/counters are created.
- Good: Owner promotes Alice to moderator on board A; Alice can close board A topics but not board B topics.
- Good: Parent board lists child boards in board detail and directory UI without exposing hidden private children.
- Base: New-topic UI prefills `post_template` and shows required/allowed tag chips.
- Bad: Frontend hides invalid tags, but backend still accepts topics missing required tags.

### 6. Tests Required

- API tests for required/allowed tag validation and no partial topic creation on failure.
- API tests for settings permission and required-vs-allowed validation.
- API tests for scoped board moderator permissions across two boards.
- API tests for child board visibility in board detail/list responses.
- Migration clean upgrade: `alembic upgrade head`.
- Quality gates: `ruff check app tests alembic` and `pytest -q`.

### 7. Wrong vs Correct

#### Wrong

```python
tags = await self._resolve_tags(payload.tags)
topic = Topic(tags=tags)
```

#### Correct

```python
normalized_tags = self._normalized_topic_tag_names(payload.tags)
await self._validate_board_topic_tags(board, normalized_tags)
tags = await self._resolve_tags(normalized_tags)
topic = Topic(tags=tags)
```

