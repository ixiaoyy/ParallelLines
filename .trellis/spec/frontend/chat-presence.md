# Chat and Presence UI Contract (Retired)

## Scenario: Chat feature removed from product navigation

### 1. Scope / Trigger

- Trigger: any attempt to reintroduce chat routes, channel lists, message composers, presence display, or SSE stream handling.
- The previous implementation under `pages/chat/`, `features/chat/`, `queryKeys.chat*`, and the `/chat` page route has been removed.

### 2. Current Contract

- The app shell must not show a Chat navigation entry on desktop or mobile.
- `/chat` is retained only as a legacy redirect to `home`; it must not lazy-load a chat page or require chat API data.
- Frontend code must not call `/api/v1/chat/*` endpoints or define chat-specific TanStack Query keys.
- Do not re-add chat UI without a new product decision and a fresh cross-layer spec.

### 3. Validation

- `rg "features/chat|pages/chat|queryKeys\.chat|/api/v1/chat|ChatPage" apps/web/src` should return no active frontend module references.
- `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`, and `pnpm --dir apps/web build` should pass.
