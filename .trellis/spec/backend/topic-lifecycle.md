# Backend Topic Lifecycle Contract

## Scenario: Close, pin, move, split, and merge topics

### 1. Scope / Trigger

- Trigger: changing moderator-only lifecycle actions for topics and their posts.
- Applies to `apps/api/app/api/v1/topics.py`, `schemas/forum.py`, `services/forum.py`, `models/forum.py`, `models/moderation.py`, Alembic migrations, and related topic/post notification/upload/revision rows.
- This is a cross-layer contract: API payloads, DB counters, public reads, audit logs, and frontend mutations must stay aligned.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Payload | Return |
|---|---|---|---|
| `PUT /api/v1/topics/{topic_id}/lifecycle` | board owner/moderator, global moderator/admin | `TopicLifecycleRequest` | `TopicResponse` |
| `POST /api/v1/topics/{topic_id}/move` | source + target board moderator | `TopicMoveRequest` | `TopicResponse` |
| `POST /api/v1/topics/{topic_id}/split` | source + target board moderator | `TopicSplitRequest` | `TopicLifecycleResponse` |
| `POST /api/v1/topics/{topic_id}/merge` | source + target board moderator | `TopicMergeRequest` | `TopicLifecycleResponse` |

Pydantic payloads in `apps/api/app/schemas/forum.py`:

```python
class TopicLifecycleRequest(BaseModel):
    status: Literal["open", "closed", "archived"] | None = None
    pinned: bool | None = None
    note: str | None = None

class TopicMoveRequest(BaseModel):
    board_id: str | None = None
    board_slug: str | None = None
    note: str | None = None

class TopicSplitRequest(BaseModel):
    title: str
    post_ids: list[str]
    board_id: str | None = None
    board_slug: str | None = None
    note: str | None = None

class TopicMergeRequest(BaseModel):
    target_topic_id: str
    note: str | None = None
```

DB/model additions:

- `topics.merged_into_topic_id -> topics.id`, nullable, `ON DELETE SET NULL`.
- `TopicResponse.merged_into_topic_id: str | None`.
- `AuditLog.action` must allow `topic_status_changed`, `topic_pinned_changed`, `topic_moved`, `topic_split`, and `topic_merged`.

### 3. Contracts

- Permission source of truth is moderation permission, not trust level:
  - global `admin` / `moderator`; or
  - `BoardMember.role in ('owner', 'moderator')` on every board touched by the operation.
- Closing/archiving:
  - `status='closed'` or `status='archived'` blocks `ForumService.reply_to_topic` with `ValidationError("topic_closed")`;
  - reopening sets `status='open'` and allows replies again.
- Pinning:
  - `Topic.pinned` changes write a `topic_pinned_changed` audit log when the value changes.
- Moving:
  - target board must differ from source board;
  - source and target `Board.topic_count` / `Board.post_count` are adjusted by the full visible topic post count;
  - topic slug is re-uniquified if the target board already has that slug;
  - upload board references move with the topic/posts;
  - returned `TopicResponse.board_slug` must reflect the target board, so the service must refresh or set the relationship after `board_id` changes.
- Splitting:
  - first post cannot be split away;
  - selected posts must belong to the source topic and must not be hidden;
  - selected posts move to a new topic, keep chronological order, and are renumbered from `1`;
  - remaining source posts are renumbered from `1`;
  - source/target topic counters and source/target board counters are recomputed;
  - `Notification`, `Upload`, and `PostRevision` rows for moved posts must point at the new topic/board.
- Merging:
  - source and target topics must differ;
  - all source posts append after the target's existing posts and are renumbered sequentially;
  - source topic is soft-hidden (`status='hidden'`, `deleted_at` set) and stores `merged_into_topic_id=target.id`;
  - `GET /api/v1/topics/{source_id}` returns `409 topic_merged` with `details.target_topic_id` when the requester can access the target board;
  - tags are merged without duplicate `topic_tags` rows;
  - `TopicRead` rows are merged by keeping the maximum read post number per user;
  - `Notification`, `Upload`, and `PostRevision` rows for moved posts must point at the target topic/board.
- Each action writes an `audit_logs` row in the same transaction with enough `data` to reconstruct source board, target board/topic, moved post counts, and moderator note.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Ordinary user updates lifecycle/move/split/merge | `moderation_forbidden` / 403 |
| Target board does not exist | `board_not_found` / 404 |
| Move to the same board | `topic_already_in_board` / 422 |
| Reply to `closed` or `archived` topic | `topic_closed` / 422 |
| Split includes the first post | `cannot_split_first_post` / 422 |
| Split includes missing/hidden/foreign post | `split_posts_not_found` / 404 or validation error |
| Merge source into itself | `cannot_merge_same_topic` / 422 |
| Public read of merged source topic by allowed user | `topic_merged` / 409 with `target_topic_id` |
| Public read of merged source topic without target access | `topic_not_found` / 404 |

### 5. Good/Base/Bad Cases

- Good: board owner closes a topic, verifies replies are blocked, reopens it, and sees a `topic_status_changed` audit row.
- Good: moderator splits selected reply IDs into a new topic and tests both topics have contiguous `post_number` values.
- Base: moderator moves a topic to another board and the response includes the new `board_slug` plus adjusted board counters.
- Bad: service changes `Topic.board_id` but does not update `topic.board`, returning a stale `board_slug` to the client.
- Bad: merge updates `Post.topic_id` only and forgets `Notification`, `Upload`, `PostRevision`, or `TopicRead` rows.

### 6. Tests Required

- `apps/api/tests/test_topic_lifecycle.py` must assert:
  - ordinary users cannot lifecycle/move/split/merge;
  - board owner/global moderator can close, pin, archive, and reopen;
  - closed/archived topics block replies;
  - moving updates returned board slug and board counters;
  - splitting rejects first post and produces contiguous post numbers/counters;
  - merging appends posts, hides source, returns `409 topic_merged`, and writes audit logs.
- Regression set for touched domains:
  - `pytest apps/api/tests/test_topic_lifecycle.py apps/api/tests/test_forum_core.py apps/api/tests/test_moderation.py -q --tb=short`;
  - full backend suite before finishing: `pytest apps/api/tests -q --tb=short`;
  - `ruff check apps/api/app apps/api/tests apps/api/alembic`.
- Migration verification: run Alembic upgrade on a clean DB path before release.

### 7. Wrong vs Correct

#### Wrong

```python
topic.board_id = payload.board_id
await session.commit()
return topic  # may still serialize the old board relationship
```

#### Correct

```python
topic.board_id = target_board.id
topic.board = target_board
self._add_audit_log(action="topic_moved", target_id=topic.id, board_id=target_board.id)
await session.commit()
return await self.get_topic(topic.id, current_user=current_user)
```

#### Wrong

```python
await session.execute(update(Post).where(Post.topic_id == source.id).values(topic_id=target.id))
source.deleted_at = utcnow()
```

#### Correct

```python
await self._move_post_related_rows(source_post_ids, topic_id=target.id, board_id=target.board_id)
await self._merge_topic_reads(source.id, target.id)
source.status = "hidden"
source.deleted_at = utcnow()
source.merged_into_topic_id = target.id
```
