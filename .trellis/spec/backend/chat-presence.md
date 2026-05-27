# Chat and Presence Contract (Retired)

## Scenario: Chat API, realtime bus, and storage removed

### 1. Scope / Trigger

- Trigger: any attempt to reintroduce chat channels, direct chat, board-bound chat, message history, SSE streams, or online/typing presence.
- The previous implementation under `app/models/chat.py`, `schemas/chat.py`, `services/chat.py`, `services/chat_realtime.py`, `api/v1/chat.py`, and `tests/test_chat_presence.py` has been removed.

### 2. Current Contract

- `/api/v1/chat/*` endpoints are no longer registered in `app/api/v1/router.py`.
- Chat ORM models, schemas, services, realtime bus, spam chat-message guard, and chat runtime settings must stay absent.
- Migration `0045_remove_chat_feature` drops the obsolete `chat_presence`, `chat_channel_members`, `chat_messages`, and `chat_channels` tables.
- OpenAPI snapshots and generated frontend types must not contain chat paths or chat DTO schemas.
- Do not re-add chat backend functionality without a new product decision, privacy/data-retention plan, and fresh cross-layer spec.

### 3. Validation

- `rg "app\.models\.chat|app\.schemas\.chat|app\.services\.chat|/api/v1/chat|chat_realtime|rate_limit_chat" apps/api/app apps/api/tests` should return no active references.
- Run backend lint on touched code and OpenAPI snapshot checks after route removal.
