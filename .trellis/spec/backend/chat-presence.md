# Chat and Presence Contract

## Scenario: Realtime channel chat, permissioned history, and presence snapshots

### 1. Scope / Trigger

- Trigger: adding or changing chat channels, direct chat, board-bound chat, message history,
  SSE streams, or online/typing presence.
- Applies to `app/models/chat.py`, `schemas/chat.py`, `services/chat.py`, `api/v1/chat.py`,
  Alembic migrations, and privacy cleanup paths.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/chat/channels` | user | Lists channels current user may access. |
| `POST /api/v1/chat/channels` | user | Creates `public`, `board`, or `direct` chat channel. |
| `GET /api/v1/chat/channels/{channel_id}/messages?before_id=&after_id=&q=&limit=` | user | Reads paginated/searchable channel history. |
| `POST /api/v1/chat/channels/{channel_id}/messages` | user | Sends a chat message. |
| `GET /api/v1/chat/channels/{channel_id}/presence` | user | Lists online/typing users in channel. |
| `PUT /api/v1/chat/channels/{channel_id}/presence` | user | Heartbeat and typing update. |
| `GET /api/v1/chat/channels/{channel_id}/stream?after_id=&once=` | user | SSE snapshot for reconnect-safe new messages and presence. |

Database tables:

- `chat_channels`: public/board/direct channel metadata and counters.
- `chat_messages`: channel messages with raw text, soft-delete timestamp, and author.
- `chat_channel_members`: direct-channel membership and member read position.
- `chat_presence`: per-channel online/typing snapshot.

### 3. Contracts

- Chat endpoints require an authenticated active user.
- `public` channels are readable by all authenticated users.
- `board` channels inherit board visibility:
  - public board: authenticated users may access;
  - private/unlisted board: only owner/member may access.
- `direct` channels are readable only when `chat_channel_members` contains the current user.
- Unauthorized private/direct channel reads return `chat_channel_not_found` / 404 to avoid leaking
  channel existence.
- `POST /messages` trims `raw_text`; empty text returns `chat_message_empty` / 422.
- Message history:
  - default and `before_id` pagination return ascending messages for display;
  - `after_id` returns messages created after the anchor for reconnect;
  - `q` filters `raw_text` through ORM parameter binding.
- SSE event name is `chat`, with data `{ "messages": ChatMessageResponse[], "presence": ChatPresenceResponse[] }`.
- `presence.typing=true` expires after a short TTL; `online=true` is derived from `last_seen_at`.
- Account deletion/anonymization removes channel memberships and presence rows; retained messages
  continue pointing at the anonymized user placeholder.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Visitor without token accesses chat | Auth failure / 401 |
| Stranger opens private board channel | `chat_channel_not_found` / 404 |
| Direct chat across block boundary | `chat_direct_blocked` / 422 |
| Board channel without `board_slug` | `chat_board_required` / 422 |
| `after_id` from another channel | `chat_message_not_found` / 404 |
| Reconnect with `after_id=last_seen_message` | Stream first frame includes newer messages |
| Typing heartbeat expires | `typing=false` after TTL-derived response |
| Search query has wildcard characters | Bound ORM query; no raw SQL concatenation |

### 5. Good/Base/Bad Cases

- Good: private-board owner creates a board chat; outsider cannot list or open it, member can.
- Good: client reconnects with last message ID and receives missed messages in the first SSE frame.
- Base: user sends a message, channel counter/last-message timestamp update, and own presence is
  refreshed in the same request.
- Bad: frontend hides a private channel while `/chat/channels/{id}/messages` still returns history.
- Bad: using Redis as the only source of chat history; database remains source of truth.

### 6. Tests Required

- Default roadmap smoke: `pytest tests/test_chat_presence.py -q`.
- Assertions:
  - private board channel ACL hides channel and messages from outsiders;
  - message send persists and search returns history;
  - SSE `after_id` returns missed messages;
  - presence heartbeat exposes online/typing user.
- Run `ruff check` on touched chat, router, model, migration, and test files.

### 7. Wrong vs Correct

#### Wrong

```python
message = await session.get(ChatMessage, message_id)
return message.raw_text
```

#### Correct

```python
page = await ChatService(session).list_messages(channel_id, current_user, after_id=last_id)
return ApiResponse(data=page)
```

The service owns channel ACL, pagination anchors, and response mapping.
