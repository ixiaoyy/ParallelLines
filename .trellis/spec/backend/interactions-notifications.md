# Backend Interactions and Notifications Contract

## Scenario: Persisted interactions and notification fan-out

### 1. Scope / Trigger

- Trigger: implementing likes, bookmarks, board follows, and notifications touches API routes, service transactions, database tables, response schemas, and tests.
- Use this contract whenever changing `reactions`, `bookmarks`, `notifications`, `board_members`, or notification creation during topic/post writes.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `PUT` | `/api/v1/boards/{slug}/follow` | yes | Follow board or update notification level |
| `DELETE` | `/api/v1/boards/{slug}/follow` | yes | Unfollow board |
| `PUT` | `/api/v1/posts/{post_id}/like` | yes | Like a post idempotently |
| `DELETE` | `/api/v1/posts/{post_id}/like` | yes | Unlike a post idempotently |
| `PUT` | `/api/v1/topics/{topic_id}/like` | yes | Like a topic idempotently |
| `DELETE` | `/api/v1/topics/{topic_id}/like` | yes | Unlike a topic idempotently |
| `PUT` | `/api/v1/topics/{topic_id}/bookmark` | yes | Bookmark a topic idempotently |
| `DELETE` | `/api/v1/topics/{topic_id}/bookmark` | yes | Remove topic bookmark idempotently |
| `GET` | `/api/v1/notifications?unread_only=&limit=` | yes | List current user's notifications |
| `PUT` | `/api/v1/notifications/read` | yes | Mark selected or all notifications read |
| `GET` | `/api/v1/notifications/stream?poll_seconds=&limit=` | yes | SSE stream for unread count and recent unread notifications |
| `GET` | `/api/v1/topics/{topic_id}/notification-level` | yes | Read current user's topic read/notification level |
| `PUT` | `/api/v1/topics/{topic_id}/notification-level` | yes | Set current user's topic notification level |

Database signatures:

- `reactions(target_type, target_id, user_id, type)` has unique constraint `uq_reactions_target_user_type`.
- `bookmarks(target_type, target_id, user_id)` has unique constraint `uq_bookmarks_target_user`.
- `notifications(user_id, type, topic_id, post_id, actor_id, data, read_at)` has index `(user_id, read_at, created_at)`.

### 3. Contracts

- All routes return the existing envelope: `{ "data": ..., "meta": {} }`.
- Follow request body: `{ "notification_level": "muted|normal|tracking|watching" }`.
- Topic notification request body: `{ "notification_level": "muted|normal|tracking|watching" }`.
- Topic notification response:
  `{ "topic_id": string, "notification_level": "muted|normal|tracking|watching", "last_read_post_number": number }`.
- Interaction response: `{ "target_type": "post|topic", "target_id": string, "active": boolean, "count": number }`.
- `TopicResponse` social fields: `liked_by_me`, `bookmarked_by_me`, `bookmark_count`, and
  `share_url` must be populated by the service decoration layer before schema serialization.
- `PostResponse` social fields: `liked_by_me` and `share_url` must be populated consistently for
  topic detail post streams.
- Notification list response: `{ "notifications": NotificationResponse[], "unread_count": number }`.
- Mark-read request: `{ "ids": string[] | null }`; omit or pass `null` to mark all unread notifications for the current user.
- Notification stream event: SSE event `notifications` with data `{ "unread_count": number, "notifications": NotificationResponse[] }`; emit heartbeats as SSE comments when unchanged.
- Notification `data` is a small JSON summary only; include navigational fields such as `topic_title`, `topic_slug`, `post_number`, and `board_slug` when available, but do not store raw post bodies or secrets in notification payloads.
- Write-path services enqueue `create_notification` background jobs with `commit=False`; the unified background worker creates `notifications` rows after the request transaction commits.
- Notification jobs must include deterministic idempotency keys so repeated enqueue attempts do not create duplicate notification rows.
- Topic muted state is authoritative for all topic-scoped notification fan-out. If a recipient has
  `topic_reads.notification_level="muted"`, suppress `replied`, `mentioned`, `liked`, and
  `topic_new_post` notifications for that topic.
- First-time non-self likes/bookmarks may award the content owner through `GrowthService`; duplicate
  like/bookmark calls must not create duplicate reward events, and unlike/unbookmark does not revoke
  already-earned points.
- `watching` and `tracking` topic read states receive `topic_new_post` fan-out when they were not
  already notified by a direct reply/mention notification.
- Board members with `notification_level in ("watching", "tracking")` receive `board_new_topic`
  fan-out. `normal` and `muted` board levels remain membership/follow state but do not trigger
  board-new-topic fan-out.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Unknown board/topic/post | Raise `NotFoundError` with `board_not_found`, `topic_not_found`, or `post_not_found` |
| Board owner unfollows owned board | Raise `ValidationError("board_owner_cannot_unfollow")` |
| Duplicate like/bookmark/follow | Return current state without inserting duplicate rows |
| Unlike/unbookmark/unfollow missing row | Return inactive state without error |
| Private-board topic/post interaction by non-member | Raise the same `NotFoundError` as the read path; do not leak target existence |
| Notification IDs from another user | Do not update them; never leak existence |
| Worker has not processed queued notification | Notification list stays unchanged until the queued job succeeds |
| Muted topic recipient is replied to, mentioned, liked, or watching | Do not enqueue a topic notification job for that recipient |
| Unknown/private topic notification-level read or write | Raise `NotFoundError("topic_not_found")` using the same board ACL checks as topic detail |

### 5. Good/Base/Bad Cases

- Good: user likes the same post twice; row count remains 1 and post/topic like counters remain 1.
- Good: authenticated topic/post detail responses include current-user like/bookmark flags so the UI
  can render real active states without local guesses.
- Base: user replies to a topic; topic author receives `replied`; mentioned users receive `mentioned`; tracking readers receive `topic_new_post`.
- Good: user mutes a topic; later replies, mentions, likes, and watcher fan-out for that topic are
  suppressed for that user, while other watchers still receive their notifications.
- Bad: router manually commits a reaction or constructs SQL; service must own the transaction and counter updates.

### 6. Tests Required

- API test for follow/like/bookmark idempotency and counter/cache behavior.
- API smoke for topic like route and response `active/count` behavior; avoid broad per-task matrices
  unless the interaction contract changes materially.
- Service or API test proving duplicate rows cannot be created through repeated calls.
- Notification test proving reply + mention fan-out creates queued jobs and, after draining the worker, unread records.
- Preference matrix test proving muted topic suppresses `replied`, `mentioned`, and `liked`, and
  watching/tracking topics receive `topic_new_post`.
- API tests for `GET|PUT /topics/{topic_id}/notification-level`, including default `normal` when no
  `topic_reads` row exists.
- Mark-read test proving only the current user's unread notifications are updated.
- Migration check on a clean MySQL database URL.

### 7. Wrong vs Correct

#### Wrong

```python
# Router mutates ORM and commits directly.
post.like_count += 1
await session.commit()
```

#### Correct

```python
# Router delegates to the transactional service.
state = await InteractionService(session).like_post(post_id, current_user)
return ApiResponse(data=state)
```
