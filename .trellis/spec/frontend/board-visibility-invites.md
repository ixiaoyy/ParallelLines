# Frontend Board Visibility and Invites Contract

## Scenario: Invite-only boards and invite management UI

### 1. Scope / Trigger

- Trigger: changing board list rendering, invite-only board UI, invite management, or frontend handling of private board reads.
- Applies to `features/boards/`, `features/invites/`, `pages/invites/`, `pages/home/components/HomeLeftRail.vue`, `app/router.ts`, and `AppShell.vue`.

### 2. Signatures

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `fetchBoards()` | `GET /api/v1/boards` | visible `BoardResponse[]` |
| `createBoard(payload)` | `POST /api/v1/boards` | `BoardResponse` |
| `fetchMyBoardInvites()` | `GET /api/v1/invites` | `MyBoardInvitesResponse` |
| `createBoardInvite(payload)` | `POST /api/v1/invites` | `BoardInviteResponse` |
| `acceptBoardInvite(id)` | `PUT /api/v1/invites/{id}/accept` | `BoardInviteResponse` |
| `declineBoardInvite(id)` | `PUT /api/v1/invites/{id}/decline` | `BoardInviteResponse` |
| `revokeBoardInvite(id)` | `PUT /api/v1/invites/{id}/revoke` | `BoardInviteResponse` |

Route:

- `/invites` (`name: "my-invites"`) is the logged-in user's invite center.

### 3. Contracts

- `BoardSummary.visibility` must preserve backend `visibility` so UI can separate public and invite-only/private boards.
- Home left rail groups visible boards into:
  - `公共版块`: `visibility === "public"`
  - `邀请版块`: `visibility !== "public"`
- The frontend must trust backend filtering for privacy; do not render client-side fixtures for private boards.
- Invite write actions must use `features/invites/queries.ts`; components must not call `fetch` directly.
- Unauthenticated users visiting `/invites` see a login guidance state and are redirected to `/auth?redirect=/invites` for writes.
- Accepting or revoking an invite invalidates both `queryKeys.invites` and `queryKeys.boards`.
- Regular users create invite-only boards from the invite center by sending `visibility: "private"`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Anonymous opens `/invites` | Login guidance, no invite API mutation |
| User has no private boards | Invite form explains to create a board first |
| Invite action succeeds | Status message shown, invites and boards queries invalidated |
| Invite action fails because stale/processed | Visible failure message; UI state preserved |
| Accepted private board appears in `/boards` response | Left rail shows it under `邀请版块` |

### 5. Good/Base/Bad Cases

- Good: `HomeLeftRail.vue` groups `props.boards` by `visibility`, but does not try to bypass backend access control.
- Base: user creates a private board from `/invites`, invites another registered username, and sees the pending invite in managed list.
- Bad: route page imports `apiPost` directly instead of using `useCreateBoardInvite()`.
- Bad: hard-coding private board samples in production when API returns an empty list.

### 6. Tests Required

- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- Smoke/component coverage should eventually visit `/invites`, create a private board, send an invite, accept it as target user, and verify the board appears under `邀请版块`.

### 7. Wrong vs Correct

#### Wrong

```ts
const privateBoards = mockBoards.filter((board) => board.visibility === "private");
```

#### Correct

```ts
const privateBoards = computed(() =>
  props.boards.filter((board) => board.visibility !== "public"),
);
```
