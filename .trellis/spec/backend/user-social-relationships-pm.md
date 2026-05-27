# Backend User Relationships and Private Messages Contract

## Scenario: Follow/ignore/block users and participant-only private message topics

### 1. Scope / Trigger

- Trigger: changing user follow/ignore/block state, notification suppression by user relationship, private message topics, or private-message ACL.
- Applies to `app/models/social.py`, `app/services/social.py`, `app/api/v1/users.py`, `app/services/forum.py`, `schemas/users.py`, `models/forum.py`, notification fan-out, migrations, and tests.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/api/v1/users/{username}/relationship` | user | Return current user's relationship state with target user |
| `PUT` | `/api/v1/users/{username}/follow` | user | Follow target user |
| `DELETE` | `/api/v1/users/{username}/follow` | user | Unfollow target user |
| `PUT` | `/api/v1/users/{username}/ignore` | user | Ignore target user |
| `DELETE` | `/api/v1/users/{username}/ignore` | user | Stop ignoring target user |
| `PUT` | `/api/v1/users/{username}/block` | user | Block target user |
| `DELETE` | `/api/v1/users/{username}/block` | user | Unblock target user |
| `GET` | `/api/v1/users/messages?limit=` | user | List private message topics where current user is a participant |
| `POST` | `/api/v1/users/messages` | user | Create a private message topic |

Database signatures:

- `user_relationships(actor_user_id, target_user_id, relationship_type)` unique.
- `private_message_participants(topic_id, user_id)` unique.
- `topics.topic_type`: `"regular" | "private_message"`.
- `topics.visibility`: `"public" | "private_message"`.

Payloads:

```json
{
  "participant_usernames": ["alice"],
  "title": "私信主题",
  "raw_md": "第一条私信"
}
```

Relationship response:

```json
{
  "target_user_id": "1",
  "target_username": "alice",
  "following": true,
  "ignored": false,
  "blocked": false,
  "followed_by": false
}
```

### 3. Contracts

- Public topic/feed/search/profile lists must exclude `topics.visibility="private_message"`.
- Public topic/feed/search/profile lists and public topic post streams must exclude authors the
  current user has ignored or blocked; direct reads of a public topic authored by an ignored/blocked
  user return `404 topic_not_found`.
- `GET /topics/{topic_id}` and `/topics/{topic_id}/posts` allow private-message access only when `private_message_participants` contains current user.
- Stranger access to a private-message topic returns `404 topic_not_found`, not participant metadata.
- Creating a private message inserts:
  - one `Topic(topic_type="private_message", visibility="private_message")`;
  - first `Post(post_number=1)`;
  - one `PrivateMessageParticipant` row per participant including creator;
  - `private_message` notifications for other participants unless a relationship suppresses notification.
- Followed-user public topic creation enqueues `user_new_topic` notifications to followers.
- `ignore` and `block` suppress notifications from the target user to the actor.
- `block` is a hard boundary: it removes follow relationships in both directions and prevents private-message creation across that boundary.
- Private message replies reuse normal post creation and enqueue `private_message` notifications to other participants; they must not be indexed into public search.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Follow/ignore/block self | `422 relationship_self_not_allowed` |
| Follow across any block boundary | `422 relationship_blocked` |
| Create PM without another participant | `422 private_message_participant_required` |
| Create PM with missing/inactive user | `404 user_not_found` |
| Create PM across block boundary | `422 private_message_blocked` |
| Stranger reads PM topic/posts | `404 topic_not_found` |
| Ignored/blocked actor triggers notification | Notification job is not enqueued |
| Block active after follow | Follow state becomes false |

### 5. Good/Base/Bad Cases

- Good: Alice follows Bob; Bob creates a public topic; Alice receives `user_new_topic`.
- Good: Alice blocks Bob; Bob cannot create a private message with Alice and Alice receives no Bob notifications.
- Base: Alice creates a private message with Bob; both can read/reply; Carol receives `404`.
- Bad: hiding private messages only in the frontend while leaving `/topics/{id}` publicly readable.

### 6. Tests Required

- API tests for follow/block state and followed-user notification fan-out.
- API tests for private-message participant-only access and reply notification.
- API test proving private-message creation is blocked across a block boundary.
- Migration clean upgrade: `alembic upgrade head`.
- Quality gates: `ruff check app tests alembic` and `pytest -q`.
