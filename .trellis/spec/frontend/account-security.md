# Frontend Account Security UI Contract

## Scenario: account recovery, 2FA login, and security settings page

### 1. Scope / Trigger

- Trigger: any change to `features/auth/*`, `/auth`, `/security`, topbar auth navigation, or
  `UserPublic`/`TokenPair` DTOs.
- The UI must keep no-enumeration semantics for password reset and must not persist tokens until
  login, email verification, or 2FA verification returns a full `TokenPair`.

### 2. Signatures

Routes:

- `/auth?mode=forgot`
- `/auth?mode=register`
- `/auth?redirect=/target`
- `/security`

Auth model additions:

- `UserPublic.two_factor_enabled: boolean`
- `TokenPair.session_id: string | null`
- `LoginResponse`: optional token/user fields plus `two_factor_required` and `challenge_token`.
- Security DTOs: `SessionResponse`, password reset, email change, 2FA setup/enable/disable, and
  OAuth provider response types.

Composables:

- `useLogin()` stores tokens only when `LoginResponse.two_factor_required === false`.
- `useVerifyTwoFactorLogin()` stores the returned `TokenPair`.
- `useRequestPasswordReset()` and `useConfirmPasswordReset()` power `/auth?mode=forgot`.
- `useSessions()`, `useRevokeSession()`, and `useRevokeOtherSessions()` back `/security`.
- `useTwoFactorSetup()`, `useTwoFactorEnable()`, `useTwoFactorDisable()`,
  `useRegenerateRecoveryCodes()` back the 2FA panel.

### 3. Contracts

- `/auth` login handles two states:
  1. password accepted but `two_factor_required=true`: show second-factor form, keep tokens empty;
  2. full token pair: persist tokens and redirect.
- Forgot-password UI always says "if the email exists" and never displays account existence.
- Password reset confirm requires the registered email, the emailed 6-digit reset code, and two
  matching new-password entries; successful reset returns the user to login and does not auto-login.
- Password creation/change inputs should use a right-side show/hide eye affordance while preserving
  native autocomplete values.
- `/security` is visible from topbar/mobile nav only for logged-in users. Logged-out users see a
  clear login CTA.
- Security page panels:
  - password change;
  - email change request/confirm token;
  - TOTP setup/enable/disable/recovery-code regeneration;
  - active sessions list with current-session marker and revoke actions;
  - OAuth provider discovery.
- The current session is not revoked from the sessions list UI; users use logout for that path.
- Recovery codes are shown once immediately after enable/regenerate and should be copied by users.
- `useLogout()` attempts server logout when a token exists, but always clears local storage even if
  the server session is already expired.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Login returns `two_factor_required` | Show 2FA form; do not write tokens |
| Bad 2FA code | Show "二次验证码或恢复码不正确"; stay on challenge form |
| Password-reset request | Show a uniform success/failure message, e.g. "重置验证码已发送，请查收邮件。" |
| Invalid reset token | Show invalid/expired token message |
| Change password succeeds | Clear fields; tell user other sessions were revoked |
| Email exists | Show "该邮箱已被其他账号使用" |
| Invalid email-change token | Show invalid/expired token message |
| No sessions | Show empty state |
| Current session revoke click | Block client-side and tell user to logout |
| No OAuth providers | Show "暂未启用外部登录提供方" |

### 5. Good/Base/Bad Cases

- Good: login → 2FA challenge → verify → redirect, with current-user cache populated from
  `TokenPair.user`.
- Good: `/security` invalidates `queryKeys.sessions` after revokes and updates
  `queryKeys.currentUser` after email confirmation/2FA changes.
- Base: local memory email mode still requires the user to paste reset/email-change tokens from the
  mail sink; the UI must not depend on dev-only token fields.
- Bad: storing a `challenge_token` in localStorage as an access token.
- Bad: showing "email not found" during forgot-password request.
- Bad: inferring 2FA status from local storage instead of `UserPublic.two_factor_enabled`.

### 6. Tests Required

- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- Browser/manual checks:
  - `/auth?mode=forgot` request and confirm forms render and validate;
  - 2FA login challenge does not mark topbar as logged in until verification succeeds;
  - `/security` lists active sessions and revoke buttons refresh the list;
  - topbar/mobile nav shows `安全` only when `useCurrentUser()` has a user.

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
