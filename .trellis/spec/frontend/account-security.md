# Frontend Account Security UI Contract

## Scenario: account recovery, 2FA login, and profile account settings

### 1. Scope / Trigger

- Trigger: any change to `features/auth/*`, `/auth`, `/me?panel=settings`, topbar auth navigation,
  or `UserPublic`/`TokenPair` DTOs.
- The UI must keep no-enumeration semantics for password reset and must not persist tokens until
  login, email verification, or 2FA verification returns a full `TokenPair`.

### 2. Signatures

Routes:

- `/auth?mode=forgot`
- `/auth?mode=register`
- `/auth?redirect=/target`
- `/me?panel=settings&section=account`

Auth model additions:

- `UserPublic.two_factor_enabled: boolean`
- `TokenPair.session_id: string | null`
- `LoginResponse`: optional token/user fields plus `two_factor_required` and `challenge_token`.
- Security DTOs include `SessionResponse`, password reset, email change, 2FA setup/enable/disable,
  and OAuth provider response types, but the current personal-center account settings expose only
  password and email settings.

Composables:

- `useLogin()` stores tokens only when `LoginResponse.two_factor_required === false`.
- `useVerifyTwoFactorLogin()` stores the returned `TokenPair`.
- `useRequestPasswordReset()` and `useConfirmPasswordReset()` power `/auth?mode=forgot`.
- Current account settings in `UserProfilePage.vue` use `useCurrentUser()`, `useChangePassword()`,
  `useRequestEmailChange()`, and `useConfirmEmailChange()`.
- Deferred account modules must not be mounted until reprioritized: `useSessions()`,
  `useRevokeSession()`, `useRevokeOtherSessions()`, `useTwoFactorSetup()`,
  `useTwoFactorEnable()`, `useTwoFactorDisable()`, `useRegenerateRecoveryCodes()`, and
  `useOAuthProviders()`.

### 3. Contracts

- `/auth` login handles two states:
  1. password accepted but `two_factor_required=true`: show second-factor form, keep tokens empty;
  2. full token pair: persist tokens and redirect.
- Forgot-password UI uses uniform success/failure copy and never displays account existence.
- Password reset confirm requires the registered email, the emailed 6-digit reset code, and two
  matching new-password entries; successful reset returns the user to login and does not auto-login.
- Registration and resend-verification notices should use short success/failure copy such as
  "验证码已发送，请查收邮件。"; avoid exposing expiry minutes in the page notice.
- Password creation/change inputs should use a right-side show/hide eye affordance while preserving
  native autocomplete values.
- Password/email account settings live in the own-profile settings panel, not a standalone security
  page. App-shell account navigation may link to `/me?panel=settings&section=account`; the primary
  nav should not show a separate "安全" page.
- There is no `/security` route; do not reintroduce a standalone security entry unless product scope
  changes.
- Account settings panels:
  - password change;
  - email change request/confirm token.
- Deferred from account settings for now: TOTP setup/enable/disable/recovery-code regeneration, active
  sessions list/revoke actions, and OAuth/SSO provider discovery. Route meta, hero copy, cards, and
  empty states must not promise those modules while they are deferred.
- When the active sessions panel returns, the current session is not revoked from the sessions list
  UI; users use logout for that path.
- When the 2FA panel returns, recovery codes are shown once immediately after enable/regenerate and
  should be copied by users.
- `useLogout()` attempts server logout when a token exists, but always clears local storage even if
  the server session is already expired.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Login returns `two_factor_required` | Show 2FA form; do not write tokens |
| Bad 2FA code | Show "二次验证码或恢复码不正确"; stay on challenge form |
| Password-reset request | Show a uniform success/failure message, e.g. "重置验证码已发送，请查收邮件。" |
| Invalid reset token | Show invalid/expired token message |
| Change password succeeds | Clear fields; show "密码已更新。" |
| Email exists | Show "该邮箱已被其他账号使用" |
| Invalid email-change token | Show invalid/expired token message |
| `/me?panel=settings&section=account` authenticated view | Show password and email forms inside personal-center settings; do not render 2FA, active session, OAuth, or SSO cards/copy |

### 5. Good/Base/Bad Cases

- Good: login → 2FA challenge → verify → redirect, with current-user cache populated from
  `TokenPair.user`.
- Good: personal-center account settings update `queryKeys.currentUser` after email confirmation.
- Base: local memory email mode still requires the user to paste reset/email-change tokens from the
  mail sink; the UI must not depend on dev-only token fields.
- Base: deferred account modules keep their composables/API types available, but the personal center
  should not fetch sessions, 2FA setup state, or OAuth providers while those modules are not surfaced.
- Bad: storing a `challenge_token` in localStorage as an access token.
- Bad: showing "email not found" during forgot-password request.
- Bad: inferring 2FA status from local storage instead of `UserPublic.two_factor_enabled`.
- Bad: showing 2FA, active session, OAuth, or SSO CTAs in account settings before those modules
  return to product scope.

### 6. Tests Required

- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- Browser/manual checks:
  - `/auth?mode=forgot` request and confirm forms render and validate;
  - 2FA login challenge does not mark topbar as logged in until verification succeeds;
  - `/me?panel=settings&section=account` renders password/email forms inside personal-center
    settings and does not show deferred 2FA, active session, OAuth, or SSO panels;
  - `/security` is not registered as a route;
  - topbar/mobile primary nav does not show a separate `安全` item.

### 7. Wrong vs Correct

#### Wrong

```ts
const response = await login(payload);
setAuthTokens(response.access_token!, response.refresh_token!);
```

#### Correct

```ts
const response = await login(payload);
if (response.two_factor_required) return showChallenge(response.challenge_token);
setAuthTokens(response.access_token, response.refresh_token);
```

#### Wrong

```vue
<p>邮箱不存在，请重新输入。</p>
```

#### Correct

```vue
<p>重置验证码已发送，请查收邮件。</p>
```
