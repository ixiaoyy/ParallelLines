# User Profile Settings, Directory, and Activity Frontend Contract

## Scenario: Editable profile page, public directory, and privacy-aware activity UI

### 1. Scope / Trigger

- Trigger: changing `/members/:id`, `/account`, `/users`, profile edit forms, account settings embedded in
  the profile page, user directory calls, or activity feed UI.
- Applies to `features/users/`, `pages/user/UserProfilePage.vue`, `pages/user/UserDirectoryPage.vue`,
  router, app shell navigation, and query keys.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Backend endpoint | Purpose |
|---|---|---|
| `updateMyProfile(payload)` | `PATCH /users/me/profile` | Save own profile/privacy/UI prefs |
| `fetchUserProfileById(userId)` | `GET /users/id/{user_id}` | Load public profile by stable user ID |
| `fetchUserDirectory(sort)` | `GET /users/directory` | Public member directory |
| `fetchUserActivity(username, type)` | `GET /users/{username}/activity` | Privacy-aware activity list |
| `useUpdateMyProfile(username)` | mutation | Update profile and invalidate profile/current-user/directory |
| `useUserDirectory(sort)` | query | Directory server state |
| `useUserActivity(username, type, enabled)` | query | Activity server state |
| `useChangePassword()` | mutation | Save own password from personal-center account settings |
| `useRequestEmailChange()` / `useConfirmEmailChange()` | mutations | Request and confirm own login-email change |

Routes:

- `/account` → authenticated personal center for the current user; loads `/auth/me` first and then
  reads the current user's profile through the existing user profile API.
- `/account/profile` → current user's public profile form and interface preferences.
- `/account/settings` → current user's password and login-email settings.
- `/account/preferences` → current user's email notification preferences.
- `/me` → compatibility redirect to `/account`; new navigation must not generate `/me?panel=...`.
- `/users` → member directory.
- `/members/:id` → public member profile, topics, activity, relationship actions, and relationship
  lists. The page first calls `GET /users/id/{user_id}` for stable routing, then uses the returned
  `username` for existing topics/activity/relationship endpoints.

### 3. Contracts

- User directory cards must not render email and must use API-provided public fields only.
- Own account routes show edit forms; public member routes for other users must not show edit controls.
- App shell current-user navigation should label the own profile entry as “个人中心” and link through
  `/account`, while public member links continue to use `/members/:id`.
- Own-profile settings are grouped by purpose: public profile settings and account settings. Password
  and login-email forms live under `/account/settings`; there is no standalone `/security` route.
- Profile save errors preserve form fields and show visible zh-CN copy, especially invalid URL.
- Avatar display still uses `resolveApiAssetUrl()`.
- Activity tabs should query `posts`, `likes`, and `bookmarks`; if privacy hides the feed, show an honest state.
- Profile mutation invalidates current user, profile query, and directory query.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Own account profile route | Shows profile settings form and save button |
| Other profile | Shows no edit form |
| Own account settings route | Shows password and login-email forms under `/account/settings` |
| `/me` | Redirects to `/account` without preserving old settings panel query semantics |
| Invalid URL save | Shows URL-specific error; draft remains |
| Directory load | Cards show username/display name/level/contribution, never email |
| Activity private | Shows private/unavailable state, not fake empty data |
| Avatar URL | Resolved through `resolveApiAssetUrl` |

### 5. Good/Base/Bad Cases

- Good: `UserDirectoryPage` uses `useUserDirectory(sort)` instead of fixture members.
- Good: `UserProfilePage` uses `profileDisplayName()` and `profileVisibilityLabel()` helpers.
- Good: account settings reuse auth mutations from `features/auth/queries` and show password fields
  through `PasswordField`.
- Base: self edits display name and bio, directory/profile refresh after save.
- Bad: deriving edit permission from username string alone without `/auth/me`.
- Bad: putting profile form state in Pinia/localStorage.
- Bad: keeping a parallel standalone security page with duplicate password/email forms.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- Focused manual smoke when practical: open `/users`, open `/members/:id`, open
  `/account/profile`, open `/account/settings`, edit bio/link/privacy, switch activity tabs, and confirm
  account forms render only for the authenticated user's account routes.

### 7. Wrong vs Correct

#### Wrong

```ts
const directory = [{ username: 'fixture', email: 'x@example.com' }];
```

#### Correct

```ts
const directoryQuery = useUserDirectory(sort);
```
