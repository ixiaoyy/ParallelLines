# User Profile Settings, Directory, and Activity Frontend Contract

## Scenario: Editable profile page, public directory, and privacy-aware activity UI

### 1. Scope / Trigger

- Trigger: changing `/u/:username`, `/users`, profile edit forms, user directory calls, or activity feed UI.
- Applies to `features/users/`, `pages/user/UserProfilePage.vue`, `pages/user/UserDirectoryPage.vue`,
  router, app shell navigation, and query keys.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Backend endpoint | Purpose |
|---|---|---|
| `updateMyProfile(payload)` | `PATCH /users/me/profile` | Save own profile/privacy/UI prefs |
| `fetchUserDirectory(sort)` | `GET /users/directory` | Public member directory |
| `fetchUserActivity(username, type)` | `GET /users/{username}/activity` | Privacy-aware activity list |
| `useUpdateMyProfile(username)` | mutation | Update profile and invalidate profile/current-user/directory |
| `useUserDirectory(sort)` | query | Directory server state |
| `useUserActivity(username, type, enabled)` | query | Activity server state |

Routes:

- `/me` → authenticated convenience entry that loads `/auth/me` and redirects to `/u/{currentUser.username}`;
  unauthenticated users are sent through the normal login redirect.
- `/users` → member directory.
- `/u/:username` → profile, edit form for self, public topics and activity sections.

### 3. Contracts

- User directory cards must not render email and must use API-provided public fields only.
- Own profile may show the edit form; other profiles must not show edit controls.
- App shell current-user navigation should label the own profile entry as “个人中心” and link through
  `/me`/`my-profile`, while public member links continue to use `/u/:username`.
- Profile save errors preserve form fields and show visible zh-CN copy, especially invalid URL.
- Avatar display still uses `resolveApiAssetUrl()`.
- Activity tabs should query `posts`, `likes`, and `bookmarks`; if privacy hides the feed, show an honest state.
- Profile mutation invalidates current user, profile query, and directory query.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Own profile | Shows profile settings form and save button |
| Other profile | Shows no edit form |
| Invalid URL save | Shows URL-specific error; draft remains |
| Directory load | Cards show username/display name/level/contribution, never email |
| Activity private | Shows private/unavailable state, not fake empty data |
| Avatar URL | Resolved through `resolveApiAssetUrl` |

### 5. Good/Base/Bad Cases

- Good: `UserDirectoryPage` uses `useUserDirectory(sort)` instead of fixture members.
- Good: `UserProfilePage` uses `profileDisplayName()` and `profileVisibilityLabel()` helpers.
- Base: self edits display name and bio, directory/profile refresh after save.
- Bad: deriving edit permission from username string alone without `/auth/me`.
- Bad: putting profile form state in Pinia/localStorage.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- Focused manual smoke when practical: open `/users`, open own `/u/:username`, edit bio/link/privacy, switch activity tabs.

### 7. Wrong vs Correct

#### Wrong

```ts
const directory = [{ username: 'fixture', email: 'x@example.com' }];
```

#### Correct

```ts
const directoryQuery = useUserDirectory(sort);
```
