# Frontend Notifications and Interactions Contract

## Scenario: Realtime notifications with optimistic community actions

### 1. Scope / Trigger

- Trigger: changing notification bell/center, SSE stream handling, optimistic post likes, topic bookmarks, board follows, or notification read state.
- Applies to `apps/web/src/features/notifications/`, `apps/web/src/features/interactions/`, `PostItem`, board pages, topic pages, and shared API wrappers.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Purpose |
|---|---|
| `fetchNotifications(): Promise<NotificationListResponse>` | Load current notification center state |
| `markNotificationsRead(ids?: string[]): Promise<NotificationReadResponse>` | Mark selected notifications, or all when omitted |
| `useNotificationList()` | TanStack Query server-state wrapper with local mock fallback |
| `useMarkNotificationsRead()` | Optimistic read-state mutation |
| `useNotificationsStream()` | Fetch-based SSE reader with `AbortController` cleanup |
| `useOptimisticToggle<TResponse>()` | Shared optimistic toggle helper for likes/bookmarks/follows |
| `getTopicNotificationLevel(topicId)` | Load current user's topic notification/read-state level |
| `setTopicNotificationLevel(topicId, level)` | Persist `muted|normal|tracking|watching` for a topic |
| `useTopicNotificationLevel(topicId)` | TanStack Query wrapper for topic notification level |
| `useUpdateTopicNotificationLevel(topicId)` | Mutation that updates topic notification level cache |

Backend endpoints consumed:

- `GET /api/v1/notifications?limit=20`
- `PUT /api/v1/notifications/read`
- `GET /api/v1/notifications/stream?poll_seconds=5&limit=5`
- `PUT|DELETE /api/v1/posts/{post_id}/like`
- `PUT|DELETE /api/v1/topics/{topic_id}/like`
- `PUT|DELETE /api/v1/topics/{topic_id}/bookmark`
- `PUT|DELETE /api/v1/boards/{slug}/follow`
- `GET|PUT /api/v1/topics/{topic_id}/notification-level`

### 3. Contracts

- Keep notification server state in TanStack Query under `queryKeys.notifications`; do not mirror the list in Pinia.
- `NotificationBell` owns panel open/close UI and delegates data loading/mutation to notification composables.
- SSE is parsed through runtime validation (`parseNotificationStreamPayload`) before updating query cache.
- Optimistic interactions must update local UI immediately, then reconcile with API response when `hasAccessToken()` is true.
- `useOptimisticToggle()` supports two unauthenticated modes: default local mock state for static
  prototype surfaces, and `mockWhenDisabled: false` plus `onDisabled()` for production write controls
  that must guide the visitor to login without mutating local state.
- Topic/post actions that come from real API data should read active state from DTO-backed VM fields
  (`likedByMe`, `bookmarkedByMe`) instead of hardcoded `false`.
- Notification links require `topic_slug` + `topic_id` when available; fall back to `board_slug`, then `/`.
- Topic detail toolbar owns the visible notification-level selector, but data loading/mutation stays in
  `features/notifications/queries.ts`; pages pass `notificationLevel`, `notificationPending`, and
  `canSetNotification` props down to the toolbar.
- Topic notification-level query key is `queryKeys.topicNotificationLevel(topicId)`. Mutation success
  must replace this cache entry and invalidate `queryKeys.notifications`.
- Board follow controls may send `notification_level` with `PUT /boards/{slug}/follow`; the selected
  level must be one of `muted|normal|tracking|watching` and should reuse the shared `NotificationLevel`
  type.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Missing access token on prototype-only toggle | Show mock notifications and keep optimistic toggles local |
| Missing access token on real like/bookmark controls | Show visible login guidance, route to auth when page context is available, and do not change persisted-looking state |
| Notification fetch fails | Fall back to mock list; do not crash the app shell |
| Malformed SSE frame | Ignore the frame; wait for the next valid `notifications` event |
| Stream unmount/navigation | Abort the fetch stream via `AbortController` |
| Optimistic API failure | Revert the toggled active/count values |
| Missing token for topic notification selector | Disable the selector or route to auth before mutating |
| Topic notification mutation succeeds | Toolbar status updates and `topicNotificationLevel(topicId)` cache reflects server response |
| Board notification-level selector changes while logged in | `PUT /boards/{slug}/follow` persists the selected level and reconciles follower state |

### 5. Good/Base/Bad Cases

- Good: notification stream emits `{ unread_count, notifications }`; query cache merges new unread items before older cached items.
- Base: user opens the bell, sees unread count/list, marks all as read, and count drops immediately.
- Good: user sets a topic to `muted`; selector reflects the server response and future notification
  refreshes no longer show topic-scoped notifications for that user after backend fan-out drains.
- Bad: component parses JSON directly from SSE and writes unvalidated payloads into UI state.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` must pass for notification DTOs, composables, and template bindings.
- `pnpm --dir apps/web lint` must pass with no warnings.
- `pnpm --dir apps/web build` must complete; chunk size warnings are acceptable unless they fail the build.
- Manual smoke: open the bell, mark one/all read, toggle a topic like, post like, board follow, and topic bookmark.
- Manual smoke: open a topic while logged in, switch notification level through
  normal/tracking/watching/muted, reload, and confirm the selected level persists.

### 7. Wrong vs Correct

#### Wrong

```ts
const source = new EventSource("/api/v1/notifications/stream");
source.onmessage = (event) => {
  queryClient.setQueryData(queryKeys.notifications, JSON.parse(event.data));
};
```

#### Correct

```ts
const response = await fetch(getApiUrl("/notifications/stream?poll_seconds=5&limit=5"), {
  headers: createApiHeaders(),
  signal,
});
const parsed = parseNotificationStreamPayload(JSON.parse(data) as unknown);
if (parsed) {
  queryClient.setQueryData(queryKeys.notifications, (current) =>
    mergeNotificationLists(current, parsed),
  );
}
```
