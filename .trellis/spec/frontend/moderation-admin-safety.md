# Frontend Moderation Admin and Safety Contract

## Scenario: User report actions and moderation console

### 1. Scope / Trigger

- Trigger: wiring topic/post report actions and an admin moderation panel to FastAPI moderation endpoints.
- Applies to `features/moderation/`, topic/post action bars, `pages/admin/ModerationPage.vue`, router, and top navigation.

### 2. Signatures

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `createFlag(payload)` | `POST /api/v1/moderation/flags` | `FlagResponse` |
| `fetchModerationQueue(status, limit)` | `GET /api/v1/moderation/queue` | `FlagResponse[]` |
| `updateFlagStatus(flagId, payload)` | `PUT /api/v1/moderation/flags/{flag_id}/status` | `FlagResponse` |
| `setContentHidden(type, id, hidden, payload)` | `PUT /api/v1/moderation/{topics|posts}/{id}/{hide|restore}` | `ModerationActionResponse` |
| `updateUserStatus(userId, payload)` | `PUT /api/v1/moderation/users/{user_id}/status` | `UserStatusResponse` |
| `fetchAuditLogs(limit)` | `GET /api/v1/moderation/audit-logs` | `AuditLogResponse[]` |
| `fetchReviewables(status, type, limit)` | `GET /api/v1/moderation/reviewables` | `ReviewableResponse[]` |
| `fetchMyReviewables(limit)` | `GET /api/v1/moderation/reviewables/me` | `ReviewableResponse[]` |
| `claimReviewable(id)` | `POST /api/v1/moderation/reviewables/{id}/claim` | `ReviewableResponse` |
| `releaseReviewable(id)` | `POST /api/v1/moderation/reviewables/{id}/release` | `ReviewableResponse` |
| `decideReviewable(id, payload)` | `POST /api/v1/moderation/reviewables/{id}/decide` | `ReviewableResponse` |
| `appealReviewable(id, payload)` | `POST /api/v1/moderation/reviewables/{id}/appeal` | `ReviewableResponse` |

Query composables:

- `useCreateFlag()`
- `useModerationQueue(status)`
- `useFlagStatusMutation()`
- `useContentModerationMutation()`
- `useUserStatusMutation()`
- `useAuditLogs()`
- `useReviewableQueue(status)`
- `useMyReviewables()`
- `useClaimReviewableMutation()`
- `useReleaseReviewableMutation()`
- `useReviewableDecisionMutation()`
- `useAppealReviewableMutation()`

### 3. Contracts

- Report actions live in topic and post action bars and call `useCreateFlag()`; they must not call `fetch` directly.
- Duplicate report submissions for the same visible target are backend-idempotent; the UI should treat a successful `FlagResponse` as success even if it reuses an existing `id`.
- Moderation console route is `/admin/moderation` and must be shareable/bookmarkable.
- Queue status is local UI state (`pending`, `resolved`, `rejected`, `all`); server state remains in TanStack Query under `queryKeys.moderationRoot`.
- Frontend DTOs keep backend snake_case; display helpers map only labels (`flagReasonLabel`, `flagStatusLabel`, `auditActionLabel`).
- Reviewable DTOs also keep backend snake_case and use literal unions for
  `ReviewableStatus`, `ReviewableType`, and `ReviewableDecisionAction`. UI labels must go
  through `reviewableStatusLabel` and `reviewableTypeLabel`.
- The admin moderation page should treat reviewables as the primary queue and keep legacy
  flags/audit views available. Claim/release/decision mutations must invalidate
  `queryKeys.moderationRoot` and topic feed queries.
- User-facing appeal entry lives at `/moderation/reviewables` and consumes
  `/moderation/reviewables/me`; it must not call staff queue endpoints.
- Moderation notifications with `data.reviewable_id` should link to `/moderation/reviewables`
  so affected users can find the appeal entry even when no topic URL exists.
- If no access token is present, moderation queries stay disabled and the console shows a login/permission message.
- If the backend returns 403, the console shows a permission message instead of pretending the queue is empty.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Anonymous user clicks report | Mutation throws `authentication_required`; UI remains unchanged |
| Logged-in user repeats a report on the same target | Mutation succeeds with the existing flag id; queue is not spammed |
| Moderator queue returns 403 | Console renders permission guidance |
| Empty queue for selected status | Empty state explains that no flags match |
| Empty reviewable queue | Empty state explains that flags, pending content, auto-rules, and appeals appear there |
| Reviewable already claimed by another moderator | Mutation surfaces 409; UI must not imply force-claim unless backend supports it |
| User opens `/moderation/reviewables` | Shows only own reviewables from `/reviewables/me` |
| Reviewable `appeal_available=true` | Show appeal form and post `reason`; invalidate my-reviewables after success |
| Moderation notification lacks topic fields | Link falls back to `/moderation/reviewables` when `reviewable_id` exists |
| Hide/restore succeeds | Invalidate `moderationRoot` and topic feed query |
| User status form lacks user ID | Do not send request |
| Post flag response target has `post_number` | Link points to topic route with `#post-{number}` |

### 5. Good/Base/Bad Cases

- Good: `PostItem.vue` emits a report through `useCreateFlag()` with `target_type='post'` and the post id.
- Base: moderator opens `/admin/moderation`, filters pending flags, hides content, resolves flag, and audit panel refreshes.
- Good: moderator opens the reviewable tab, claims a pending queued topic, approves it, and
  sees the queue plus public topic feed refresh through query invalidation.
- Good: affected user opens `/moderation/reviewables` from a moderation notification and
  submits an appeal without gaining access to staff-only queue data.
- Bad: page component imports `apiPut` directly or stores the moderation queue in Pinia.
- Bad: frontend sends `hide`/`delete` for a queued reviewable with no `target_id` or displays
  a force-claim button when backend returns 409 for existing assignments.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` verifies DTO/query/page types.
- `pnpm --dir apps/web lint` verifies Vue template and import quality.
- `pnpm --dir apps/web build` verifies the route-level admin page chunk compiles.
- `/moderation/reviewables` route must be covered by `pnpm --dir apps/web typecheck` and
  build; manual smoke should verify an appeal form appears when `appeal_available=true`.
- Backend `tests/test_moderation.py` remains the source of truth for permission and audit behavior.

### 7. Wrong vs Correct

#### Wrong

```ts
await fetch(`/api/v1/moderation/posts/${post.id}/hide`, { method: "PUT" });
```

#### Correct

```ts
contentMutation.mutate({ targetType: "post", targetId: post.id, hidden: true });
```
