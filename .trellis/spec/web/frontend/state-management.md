# State Management

## Current Model

The application installs Pinia in `main.ts`, but the current source tree does not
define Pinia stores. Do not introduce a store merely because the dependency is
available. Existing state is divided by ownership:

| State kind | Local pattern | Reference |
|---|---|---|
| Component interaction | `ref`, `computed`, typed events | `AdminConsoleShell.vue` |
| Server data | TanStack Vue Query | `features/*/queries.ts` |
| Navigation/filter identity | Vue Router params and query | `app/router.ts`, `shared/router/params.ts` |
| Authentication | token helpers plus the current-user query cache | `shared/api/client.ts`, `features/auth/queries.ts` |
| Browser preference/cache | narrow helper with validation and SSR guards | `interfaceTheme.ts`, `publicSettingsCache.ts` |

## Local and Derived State

- Keep drawer state, selected controls, form drafts, and element refs in the
  smallest owning component.
- Derive display values with `computed`; do not synchronize two refs with a
  watcher when one is a pure function of the other.
- Watch only for a real side effect. `AdminConsoleShell.vue` watches route changes
  to close the mobile drawer rather than to duplicate route state.
- Parents own workflow state that coordinates multiple children. Children emit
  typed intent.

## Server State

- Treat Vue Query as the source of truth for API data, loading, error, freshness,
  and mutation status.
- Reuse the singleton `queryClient` and centralized `queryKeys`.
- Keep API response data in the query cache. Create a local draft only for
  unsaved edits, then invalidate or update the cache after mutation.
- Authentication transitions must clear or reset dependent cached data.
  `resetQueryCacheForAuthChange` in `features/auth/queries.ts` is the reference.
- Use root keys such as `adminRoot`, `topicsRoot`, and `moderationRoot` when a
  mutation affects a family of views; use exact keys for isolated updates.

## URL State

Shareable filters, route identity, and deep-link context belong in route params
or query strings. Normalize `string | string[] | undefined` at the boundary with
`shared/router/params.ts` rather than casting in each page.

## Persisted Browser State

- Prefix keys with `parallellines.` and version cached payloads when their shape
  may change.
- Guard `window` and `document` access for non-browser execution.
- Parse persisted data as `unknown` and validate it before use.
- Keep persistence behind a focused helper; components should not duplicate TTL,
  cleanup, or storage-key logic.

## When a Pinia Store Is Justified

Add a store only when durable client-owned state must be written by several
unrelated branches and neither the URL, Vue Query cache, nor a narrow browser
helper owns it cleanly. Document the ownership boundary when introducing the
first store.

## Avoid

- Copying query data into global mutable state.
- Using Pinia as another cache for API responses.
- Persisting unvalidated JSON and asserting its type.
- Module-level mutable UI state that leaks between route instances.
- Watchers that create circular state synchronization.
