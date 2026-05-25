# Chat and Presence UI Contract

## Scenario: Realtime chat page with query-backed history and SSE reconciliation

### 1. Scope / Trigger

- Trigger: changing chat routes, channel list, message composer, presence display, or SSE stream
  handling.
- Applies to `pages/chat/`, `features/chat/`, `app/router.ts`, `AppShell.vue`, and
  `shared/api/queryKeys.ts`.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Backend endpoint | Purpose |
|---|---|---|
| `fetchChatChannels()` | `GET /chat/channels` | Load accessible channels |
| `createChatChannel(payload)` | `POST /chat/channels` | Create public/board/direct channel |
| `fetchChatMessages(channelId, params)` | `GET /chat/channels/{id}/messages` | Load/search history |
| `sendChatMessage(channelId, payload)` | `POST /chat/channels/{id}/messages` | Send message |
| `fetchChatPresence(channelId)` | `GET /chat/channels/{id}/presence` | Load online users |
| `updateChatPresence(channelId, payload)` | `PUT /chat/channels/{id}/presence` | Heartbeat/typing |
| `useChatStream(channelId, enabled)` | `GET /chat/channels/{id}/stream` | SSE merge for new messages/presence |

Query keys:

- `queryKeys.chatChannels`
- `queryKeys.chatMessages(channelId, q)`
- `queryKeys.chatPresence(channelId)`

Route:

- `/chat` → `ChatPage.vue`

### 3. Contracts

- Chat server state stays in TanStack Query; do not mirror channel/message lists in Pinia.
- `ChatPage.vue` must show explicit login, loading, empty, error, and permission failure states.
- SSE frames must be parsed through runtime validation before updating query caches.
- `useChatStream()` starts only when a channel is selected and an access token exists, and aborts
  its `AbortController` on channel switch/unmount.
- New streamed/sent messages merge by `id` and are sorted by `created_at`.
- Presence merges by `user.id`; typing users exclude the current user from the “正在输入” line.
- Message text is rendered as plain text (`{{ message.raw_text }}`), never as raw HTML.
- The app shell may link to `/chat`, but authenticated state controls whether the page queries.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No token opens `/chat` | Login CTA; no useful chat query |
| User has no channels | Empty state with create default public channel action |
| Selected channel becomes inaccessible | Message panel shows readable permission/error state |
| SSE drops | Query polling/manual send remains the fallback; no crash |
| Malformed SSE frame | Ignore frame and wait for next valid snapshot |
| Empty message submit | Client blocks submit; backend remains source of truth |
| Search text changes | Message query key includes search term and reloads history |

### 5. Good/Base/Bad Cases

- Good: selecting a channel updates `?channel=<id>`, refreshes presence, and starts one stream.
- Good: sending a message updates the message query cache and invalidates channel counters.
- Base: user creates “站内大厅”, sends a message, sees own online state and history search.
- Bad: using a global event bus for chat messages or appending unvalidated SSE JSON directly.
- Bad: rendering message text through `v-html`.

### 6. Tests Required

- Default roadmap scope: `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web lint`.
- OpenAPI changes must also pass `pnpm --dir apps/web openapi:check`.
- Browser/e2e chat tests are deferred unless requested or release readiness requires them.

### 7. Wrong vs Correct

#### Wrong

```ts
source.onmessage = (event) => messages.value.push(JSON.parse(event.data));
```

#### Correct

```ts
const parsed = parseChatStreamPayload(JSON.parse(data) as unknown);
if (parsed) {
  queryClient.setQueryData(queryKeys.chatMessages(id, ""), (current) =>
    mergeMessagePage(current, parsed.messages),
  );
}
```

Runtime validation and query-cache merging keep realtime data consistent with refetches.
