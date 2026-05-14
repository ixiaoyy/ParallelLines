# Frontend Composable Guidelines

## Naming

- Composables use `useXxx` names: `useTopicList`, `useCreatePost`, `useNotificationsStream`.
- Query composables live near their feature module, but shared query key factories live in `shared/api/queryKeys.ts`.

## Data Fetching

- Use TanStack Query for server state.
- Use optimistic updates only for reversible interactions: likes, bookmarks, follows, notification read state.
- Invalidate the smallest practical query scope after mutations.
- Use cursor pagination composables for topic lists and post streams.

## Browser APIs

- WebSocket/SSE logic must be wrapped in composables with cleanup on unmount.
- Local storage access must be centralized and resilient to unavailable storage.

## Anti-patterns

- Do not duplicate query keys as string literals.
- Do not store long-lived server data only in Pinia.
- Do not ignore cleanup for event listeners, intervals, or streams.
