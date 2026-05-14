# Frontend State Management

## State Categories

- Server state: TanStack Query (`boards`, `topics`, `posts`, `notifications`).
- Global client state: Pinia (`auth`, `ui preferences`, `composer draft state`).
- Local UI state: component refs (`open`, `selectedTab`, `isPreview`).
- URL state: Vue Router query params (`sort`, `tag`, `cursor`, `q`).

## Rules

- Do not duplicate server collections in Pinia.
- Composer drafts may be persisted in local storage by board/topic key.
- Auth state should be derived from `/me` and token presence; avoid trusting stale local-only profile data.
- Topic list filters belong in route query parameters so URLs are shareable.

## Anti-patterns

- No event bus for core data flow.
- No global mutable singleton outside Pinia/query client.
- No storing rendered HTML drafts without sanitization boundary.
