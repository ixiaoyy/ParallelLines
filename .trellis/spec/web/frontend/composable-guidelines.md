# Composable Guidelines

## Reusable Reactive Logic

Name reusable Vue reactive functions `useXxx`. Keep them close to their owner:

- Generic browser behavior belongs in `shared/lib/`, for example
  `useMediaQuery.ts` and `useOutsidePointerDown.ts`.
- Feature-specific interaction belongs in the feature, for example
  `features/interactions/useOptimisticToggle.ts` and
  `features/topics/useAdminTopicDelete.ts`.
- Server-state composables are grouped in the feature's `queries.ts`.

A composable must own the complete lifecycle of resources it installs.
`useMediaQuery` registers its `matchMedia` listener on mount, removes it on
unmount, supports a non-browser fallback, and returns a readonly ref.

## Reactive Parameters

When callers may supply a value, ref, or getter, accept
`MaybeRefOrGetter<T>` and read it with `toValue`. Make the query key, query
function, and enabled condition react to the same source. References:

- `features/boards/queries.ts`
- `features/admin/queries.ts`

Do not read a reactive parameter once at setup and then build a supposedly
reactive query around that stale value.

## TanStack Vue Query

- Endpoint functions live in `api.ts`; a `useQuery` or `useMutation` wrapper lives
  in `queries.ts`.
- Every server query uses a key from `shared/api/queryKeys.ts`. Add a stable key
  there rather than creating local arrays.
- Authentication-sensitive queries use `hasAccessToken()` in `enabled` or handle
  the unauthenticated result explicitly, as `useCurrentUser` does.
- Choose `staleTime`, `gcTime`, `retry`, and initial cached data deliberately.
  Shared defaults are in `shared/api/queryClient.ts`; taxonomy-specific values
  are reused by board queries.
- Successful mutations invalidate the narrowest shared root that covers every
  affected consumer. `useUpdateAdminFableSpaceAccessGrant` invalidates both the
  admin and current-user entitlement roots because both views change.
- Use `setQueryData` only when the response gives enough data for a safe exact
  cache update; still invalidate related roots when other views may be stale.

## Optimistic Interaction

For reusable optimistic UI, retain previous values, prevent concurrent toggles,
and restore state on failure. `useOptimisticToggle.ts` is the local reference.
Do not let a failed request leave counters or active state in a guessed value.

## Avoid

- Raw `fetch` or direct `apiGet` calls inside a Vue component.
- Locally invented query-key arrays.
- Watchers that mirror values already expressible as `computed`.
- Lifecycle listeners without cleanup.
- Returning writable refs when consumers should only observe the state.
- Swallowing an error unless the composable intentionally restores a safe local
  state or translates it into a documented user-facing result.
