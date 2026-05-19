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

Query composables:

- `useCreateFlag()`
- `useModerationQueue(status)`
- `useFlagStatusMutation()`
- `useContentModerationMutation()`
- `useUserStatusMutation()`
- `useAuditLogs()`

### 3. Contracts

- Report actions live in topic and post action bars and call `useCreateFlag()`; they must not call `fetch` directly.
- Moderation console route is `/admin/moderation` and must be shareable/bookmarkable.
- Queue status is local UI state (`pending`, `resolved`, `rejected`, `all`); server state remains in TanStack Query under `queryKeys.moderationRoot`.
- Frontend DTOs keep backend snake_case; display helpers map only labels (`flagReasonLabel`, `flagStatusLabel`, `auditActionLabel`).
- If no access token is present, moderation queries stay disabled and the console shows a login/permission message.
- If the backend returns 403, the console shows a permission message instead of pretending the queue is empty.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Anonymous user clicks report | Mutation throws `authentication_required`; UI remains unchanged |
| Moderator queue returns 403 | Console renders permission guidance |
| Empty queue for selected status | Empty state explains that no flags match |
| Hide/restore succeeds | Invalidate `moderationRoot` and topic feed query |
| User status form lacks user ID | Do not send request |
| Post flag response target has `post_number` | Link points to topic route with `#post-{number}` |

### 5. Good/Base/Bad Cases

- Good: `PostItem.vue` emits a report through `useCreateFlag()` with `target_type='post'` and the post id.
- Base: moderator opens `/admin/moderation`, filters pending flags, hides content, resolves flag, and audit panel refreshes.
- Bad: page component imports `apiPut` directly or stores the moderation queue in Pinia.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` verifies DTO/query/page types.
- `pnpm --dir apps/web lint` verifies Vue template and import quality.
- `pnpm --dir apps/web build` verifies the route-level admin page chunk compiles.
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
