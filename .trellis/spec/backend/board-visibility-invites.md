# Backend Board Visibility and Invite Contract

## Scenario: Private/invite-only boards and visibility-safe reads

### 1. Scope / Trigger

- Trigger: implementing or changing board visibility, board membership, invitation lifecycle, or public topic/search/user-content reads.
- Applies to `apps/api/app/models/forum.py`, `schemas/forum.py`, `services/forum.py`, `api/v1/boards.py`, `api/v1/topics.py`, `api/v1/search.py`, `api/v1/users.py`, `api/v1/tags.py`, and `api/v1/invites.py`.

### 2. Signatures

Board visibility:

- `Board.visibility == "public"`: visible to anonymous users and all logged-in users.
- `Board.visibility != "public"`: invite-only/private; visible only to users with a `BoardMember` row or the board owner.

API endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/boards` | optional | Return only boards visible to the current/anonymous user |
| `GET /api/v1/boards/{slug}` | optional | Return board detail only when visible |
| `GET /api/v1/topics`, `/search`, `/users/{username}/topics`, `/tags` | optional | Exclude private board content unless current user is a member |
| `POST /api/v1/invites` | active user | Board owner invites a registered username to a private board |
| `GET /api/v1/invites` | active user | List received pending invites, managed invites, and owned private boards |
| `PUT /api/v1/invites/{id}/accept|decline|revoke` | active user | Move invite lifecycle state |

DB table:

- `board_invitations`: `board_id`, `inviter_id`, `invitee_id`, `status`, `expires_at`, `responded_at`, `revoked_by_id`, timestamps.

### 3. Contracts

- Optional-auth public reads must use `OptionalCurrentUserDep`; invalid tokens still return `invalid_token`.
- Services, not routers, own visibility checks:
  - `ForumService._board_visible_condition(current_user)` for list/search SQL filters.
  - `ForumService._can_access_board(board, current_user)` for direct object reads.
- Privacy behavior intentionally returns `board_not_found` / `topic_not_found` for unauthorized private content to avoid leaking names/slugs.
- Creating a pending invite is idempotent for the same private board + invitee.
- Accepting an invite adds a `BoardMember(role="follower")` if one does not exist and increments `Board.follower_count` once.
- Declined/revoked/accepted invites cannot be accepted again; return `board_invite_not_pending`.
- Public boards cannot be invited into through the invite API.
- Follow/like/bookmark/share-like write paths must not bypass private board membership checks.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Anonymous lists boards | Only public boards returned |
| Stranger opens private board slug/topic id | `board_not_found` or `topic_not_found` / 404 |
| Member opens accepted invite board | 200 |
| Non-owner creates invite | `board_invite_forbidden` / 403 |
| Owner invites unknown username | `user_not_found` / 404 |
| Owner invites existing member | `board_member_exists` / 422 |
| Owner repeats pending invite | 201 with existing invite id |
| Invitee accepts pending invite | 200, invite `accepted`, board member visible |
| Wrong user accepts/revokes invite | `board_invite_forbidden` / 403 |
| Accepted/declined/revoked invite accepted again | `board_invite_not_pending` / 422 |

### 5. Good/Base/Bad Cases

- Good: `GET /topics` calls `ForumService.list_topics(..., current_user=current_user)` and applies the board-visible SQL condition.
- Base: owner creates a private board, invites a user, the invitee accepts, then sees that board in `/boards`.
- Bad: UI hides private boards but `/search?q=private` still returns private topic titles to anonymous users.
- Bad: interaction services fetch a topic by id without checking `topic.board.visibility`.

### 6. Tests Required

- `tests/test_board_invites_visibility.py` must assert:
  - anonymous/stranger board, topic, search, and user-topic reads do not leak private content;
  - owner and accepted invitee can read private content;
  - pending invite creation is idempotent;
  - only board owner can invite/revoke;
  - only invitee can accept/decline;
  - accepted invite cannot be accepted again.
- Full backend regression: `ruff check app tests alembic`, `pytest -q --tb=short`, and Alembic upgrade on a clean database.

### 7. Wrong vs Correct

#### Wrong

```python
topic = await session.get(Topic, topic_id)
return TopicResponse.from_model(topic)
```

#### Correct

```python
topic = await ForumService(session).get_topic(topic_id, current_user=current_user)
return ApiResponse(data=TopicResponse.from_model(topic))
```
