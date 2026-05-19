# Frontend Auth, User Profile, and Draft Session Contract

## Scenario: Browser auth state and public profile pages

### 1. Scope / Trigger

- Applies to `/auth`, topbar session state, `/u/:username`, authenticated composers, and browser smoke tests.
- Trigger: any change to token storage, `/auth/me` usage, login/register forms, profile DTOs, or unauthenticated publish/reply behavior.

### 2. Signatures

- Routes:
  - `/auth?mode=register&redirect=/target`
  - `/auth?redirect=/target`
  - `/u/:username`
- Storage keys:
  - `parallellines.access_token`
  - `parallellines.refresh_token`
  - `parallellines:reply-draft:<topicId>`
- Composables:
  - `useCurrentUser(): UseQueryReturnType<UserPublic | null, Error>`
  - `useLogin()` / `useRegister()` persist tokens and set `queryKeys.currentUser`.
  - `useLogout()` clears token keys and current-user cache.
- Public profile VM:
  - `UserProfile` has `id`, `username`, `avatar_url`, `role`, `status`, `created_at`, `topic_count`, `post_count`.
  - `UserProfile` must not require or display `email`.

### 3. Contracts

- Auth state is verified by `/auth/me`; if `/auth/me` fails, clear local auth tokens and treat the browser as logged out.
- Topbar shows `登录/注册` when `useCurrentUser().data` is `null`; it shows username profile link plus `退出` only for verified users.
- `/auth?mode=register` must render the register form even when reusing the same mounted auth route; route query changes must update the active tab.
- `redirect` is honored only for same-site paths beginning with `/`.
- Authenticated reply drafts must not be cleared until the post mutation succeeds.
- Unauthenticated replies must guide to login and preserve the current draft using a topic-scoped draft storage key.
- Public profile pages call `/users/{username}` and `/users/{username}/topics`; they show content counts from the public profile payload.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No token | `useCurrentUser` returns `null`; topbar shows `登录/注册`; reply attempt redirects or prompts for `/auth?redirect=...`. |
| Expired/invalid token | `/auth/me` failure clears stored tokens; edit controls are not shown. |
| Register succeeds | Tokens are stored, current-user cache is set, redirect target is pushed. |
| Logout | Tokens are removed, current-user cache becomes `null`, no page reload required. |
| Public profile payload omits email | UI still renders and shows `topic_count` / `post_count`. |
| Reply mutation fails | Draft remains in textarea/storage and an error status is visible. |
| Reply mutation succeeds | Draft textarea and `parallellines:reply-draft:<topicId>` are cleared. |

### 5. Good/Base/Bad Cases

- Good: UI register → logout → UI login → visit profile → publish/reply/edit, with token read only for test bootstrap.
- Base: API-created setup data may be used in smoke tests, but browser auth must be exercised through UI forms.
- Bad: decoding a JWT locally to decide whether edit controls are visible after `/auth/me` failed.
- Bad: clearing a composer draft immediately after emitting submit, before the mutation succeeds.

### 6. Tests Required

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web test:smoke` against a real API and Vite server should verify:
  - UI register, logout, UI login.
  - Topbar username links to `/u/:username`.
  - Profile shows authored topic and content counts payload can omit email.
  - Reply/edit flows work after verified login.
  - Unrelated user replies are hidden by only-author filtering.

### 7. Wrong vs Correct

#### Wrong

```ts
const currentUserId = computed(() => currentUserQuery.data.value?.id ?? readUserIdFromJwt());
```

#### Correct

```ts
const currentUserId = computed(() => currentUserQuery.data.value?.id ?? null);
```

#### Wrong

```ts
emit("submit", rawMd);
draft.value = "";
```

#### Correct

```ts
emit("submit", rawMd);
// Parent increments resetToken only after mutation success.
```
