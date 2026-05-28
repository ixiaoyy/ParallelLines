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
- Registration API:
  - `POST /auth/register` accepts `{ username, email, password }` and returns `RegistrationStartResponse`.
  - `POST /auth/verify-email` accepts `{ email, code }` and returns `TokenPair`.
  - `POST /auth/resend-verification` accepts `{ email }` and returns `RegistrationStartResponse`.
- Storage keys:
  - `parallellines.access_token`
  - `parallellines.refresh_token`
  - `parallellines:reply-draft:<topicId>`
- Refresh API:
  - `POST /auth/refresh` accepts `{ refresh_token }` and returns `{ access_token, token_type }`.
- Composables:
  - `useCurrentUser(): UseQueryReturnType<UserPublic | null, Error>`
  - `useLogin()` / `useVerifyEmail()` persist tokens and set `queryKeys.currentUser`.
  - `useRegister()` starts the pending verification flow and must not persist tokens.
  - `useLogout()` clears token keys and current-user cache.
- Registration response:
  - `RegistrationStartResponse.email`
  - `RegistrationStartResponse.verification_required`
  - `RegistrationStartResponse.expires_in_seconds`
  - `RegistrationStartResponse.resend_after_seconds`
  - `RegistrationStartResponse.dev_verification_code | null`
- Public profile VM:
  - `UserProfile` has `id`, `username`, `avatar_url`, `role`, `level`, `points_balance`,
    `experience_total`, `experience_to_next_level`, `level_progress_percent`, `status`,
    `created_at`, `topic_count`, `post_count`.
  - `UserProfile` must not require or display `email`.
- Current user DTO:
  - `UserPublic` has `id`, `username`, `email`, `avatar_url`, `role`, `level`,
    `points_balance`, `experience_total`, `experience_to_next_level`,
    `level_progress_percent`, `status`, `two_factor_enabled`, `created_at`.

### 3. Contracts

- Auth state is verified by `/auth/me`; when a request returns 401 and a refresh token exists, the shared API client must call `/auth/refresh`, store the new access token, and retry once before treating the browser as logged out.
- Clear local auth tokens only after refresh fails with an auth error or when no refresh token exists; transient non-auth failures must not erase stored credentials.
- Topbar shows `登录/注册` when `useCurrentUser().data` is `null`; it shows username profile link plus `退出` only for verified users.
- `/auth?mode=register` must render the register form even when reusing the same mounted auth route; route query changes must update the active tab.
- Register success means "verification email sent", not "authenticated". The UI must show a code entry step and wait for `/auth/verify-email` before redirecting.
- `dev_verification_code` is only for local/test memory delivery. Production SMTP responses must not expose the code; the UI should work when this field is `null`.
- `redirect` is honored only for same-site paths beginning with `/`.
- Authenticated reply drafts must not be cleared until the post mutation succeeds.
- Unauthenticated replies must guide to login and preserve the current draft using a topic-scoped draft storage key.
- Public profile pages call `/users/{username}` and `/users/{username}/topics`; they show content counts from the public profile payload.
- User role helpers live in `features/auth/permissions.ts`; do not scatter string checks like `role === 'admin'` across page components.
- User `level` defaults to `0` and is display/session metadata; admin permissions remain role-based.
- Profile/security growth displays use API-provided level, usable-points, and growth-value fields and must not
  duplicate backend level threshold rules. The topbar keeps the profile link compact and should not
  show point balances or detailed growth numbers.
- Login may return a 2FA challenge instead of a token pair; only `/auth/2fa/verify-login`
  may persist tokens after `two_factor_required=true`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No token | `useCurrentUser` returns `null`; topbar shows `登录/注册`; reply attempt redirects or prompts for `/auth?redirect=...`. |
| Expired access token with valid refresh token | Shared API client refreshes access token through `/auth/refresh`, retries `/auth/me`, and keeps the user logged in. |
| Expired/invalid refresh token | Refresh fails, stored tokens are cleared, and edit controls are not shown. |
| Register succeeds | Pending verification form is shown; no tokens are stored yet. |
| Verify email succeeds | Tokens are stored, current-user cache is set, redirect target is pushed. |
| Login before verification | API returns `email_not_verified`; UI tells the user to finish email activation. |
| Invalid/expired code | UI keeps the pending email and shows a field-level verification error. |
| Resend too soon | API returns `verification_resend_limited`; UI does not clear the existing code input. |
| Logout | Tokens are removed, current-user cache becomes `null`, no page reload required. |
| Public profile payload omits email | UI still renders and shows `topic_count` / `post_count`. |
| Public profile/current user includes growth fields | UI renders level/usable points/growth value as metadata and does not infer permissions from it. |
| Reply mutation fails | Draft remains in textarea/storage and an error status is visible. |
| Reply mutation succeeds | Draft textarea and `parallellines:reply-draft:<topicId>` are cleared. |

### 5. Good/Base/Bad Cases

- Good: UI register → input email code → logout → UI login → visit profile → publish/reply/edit, with token read only for test bootstrap.
- Base: API-created setup data may be used in smoke tests, but browser auth must be exercised through UI forms.
- Bad: decoding a JWT locally to decide whether edit controls are visible after `/auth/me` failed.
- Bad: clearing a composer draft immediately after emitting submit, before the mutation succeeds.
- Bad: storing auth tokens from `/auth/register`; only `/auth/login` and `/auth/verify-email` may authenticate the browser.
- Bad: checking administrator access from `level`; administrator access is `role === 'admin'`.

### 6. Tests Required

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web test:smoke` against a real API and Vite server should verify:
  - UI register, email-code activation, logout, UI login.
  - Topbar username links to `/u/:username`.
  - Profile shows authored topic and content counts payload can omit email.
  - Current-user/profile DTOs include `level`, and admin/moderation UI uses shared permission helpers.
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

#### Wrong

```ts
await registerMutation.mutateAsync(payload);
setAuthTokens(tokenPair.access_token, tokenPair.refresh_token);
```

#### Correct

```ts
const pending = await registerMutation.mutateAsync(payload);
showVerificationForm(pending.email);
const tokenPair = await verifyEmailMutation.mutateAsync({ email: pending.email, code });
setAuthTokens(tokenPair.access_token, tokenPair.refresh_token);
```
