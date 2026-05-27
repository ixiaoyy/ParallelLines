# Backend Account Recovery and Login Security Contract

## Scenario: password recovery, session devices, 2FA, and OAuth provider discovery

### 1. Scope / Trigger

- Trigger: any change to `app/api/v1/auth.py`, `app/services/auth.py`, `app/models/user.py`,
  `app/schemas/auth.py`, auth token/session validation, or account-security migrations.
- The implementation must preserve no-account-enumeration behavior for password reset and
  one-time/expiring semantics for reset and email-change tokens.

### 2. Signatures

API endpoints under `/api/v1/auth`:

| Endpoint | Request | Response |
|---|---|---|
| `POST /password-reset/request` | `{ email }` | `{ ok, expires_in_seconds }` |
| `POST /password-reset/confirm` | `{ email, token, new_password }` where `token` is the 6-digit reset code | `{ ok }` |
| `POST /password/change` | Bearer + `{ current_password, new_password }` | `{ ok }` |
| `POST /email-change/request` | Bearer + `{ new_email, password }` | `{ email, expires_in_seconds }` |
| `POST /email-change/confirm` | `{ token }` | `UserPublic` |
| `POST /2fa/setup` | Bearer + `{ password }` | `{ secret, otpauth_url }` |
| `POST /2fa/enable` | Bearer + `{ secret, code }` | `{ recovery_codes }` |
| `POST /2fa/verify-login` | `{ challenge_token, code }` | `TokenPair` |
| `POST /2fa/disable` | Bearer + `{ password, code }` | `{ ok }` |
| `POST /2fa/recovery-codes` | Bearer + `{ password, code }` | `{ recovery_codes }` |
| `GET /sessions` | Bearer | `SessionResponse[]` active sessions only |
| `DELETE /sessions/{session_id}` | Bearer | `{ ok }` |
| `POST /sessions/revoke-others` | Bearer | `{ revoked }` |
| `GET /oauth/providers` | none | `{ providers }` |

DB tables/columns:

- `users.two_factor_enabled`, `users.two_factor_secret`.
- `user_security_tokens`: stores hashed reset/email-change tokens, purpose, target email,
  optional JSON payload, expiry, and consumed timestamp.
- `user_sessions`: stores refresh token hash, user agent, IP, last seen, and revoked timestamp.
- `user_recovery_codes`: stores hashed TOTP recovery codes and used timestamp.

### 3. Contracts

- Reset codes and email-change raw tokens are delivered by `send_email` background jobs;
  `user_security_tokens` stores only HMAC hashes, expiry, attempt counts, and consumption state.
- Password reset codes expire quickly; the default TTL is 5 minutes.
- Request paths enqueue email jobs with `BackgroundJobService(..., commit=False)` and do not perform SMTP work synchronously.
- `request_password_reset` returns the same success payload for known and unknown emails.
- Consuming a reset or email-change token sets `consumed_at`; successful confirmation also
  consumes other open tokens of the same purpose for that user.
- Password reset confirmation scopes the 6-digit code by email and increments
  `user_security_tokens.attempt_count` on bad codes to prevent brute-force retries.
- Password reset revokes all sessions; password change revokes all sessions except the current
  access-token `sid`.
- `TokenPair` includes `session_id`; access and refresh JWTs include `sid`, and
  `CurrentUserDep` rejects revoked/mismatched sessions.
- Login with `two_factor_enabled=true` returns `LoginResponse(two_factor_required=true,
  challenge_token=...)` and must not create a session until `/2fa/verify-login` succeeds.
- TOTP uses 30-second steps, six digits, and a ±1 step validation window. Recovery codes are
  one-time and are marked used inside the same transaction that creates the login session.
- `/sessions` lists only active (non-revoked) sessions. Current session is marked by matching
  the access-token `sid`.
- `/oauth/providers` is a read-only capability discovery endpoint backed by
  `OAUTH_ENABLED_PROVIDERS`; provider login callbacks are not implemented yet.

### 4. Validation & Error Matrix

| Case | Expected error/behavior |
|---|---|
| Unknown password-reset email | `200` with the same `{ ok, expires_in_seconds }`; no email job/outbox token |
| Reset/email token expired or consumed | `422 invalid_reset_token` / `invalid_email_change_token` |
| Reset token reused | `422 invalid_reset_token`; password is not changed again |
| Login before 2FA verify | No `access_token`; client must submit `challenge_token` + code |
| Bad TOTP/recovery code | `401 invalid_two_factor_code` |
| Reused recovery code | `401 invalid_two_factor_code` |
| Revoked session access token | `401 invalid_token` from dependency validation |
| Revoke another user's session | `422 session_not_found` |
| Email change to existing email | `409 email_exists` |

### 5. Good/Base/Bad Cases

- Good: verified user requests reset, confirms fresh token once, all old sessions fail `/me`,
  and new password logs in.
- Good: user enables 2FA, login returns a challenge, TOTP verifies, recovery code works once.
- Base: tokens without `sid` are accepted for legacy/test compatibility, but new token pairs
  always include `sid`.
- Bad: returning different reset responses for known vs unknown emails.
- Bad: storing raw reset/recovery secrets in user tables or job logs.
- Bad: listing revoked sessions in the active sessions response.

### 6. Tests Required

- `pytest apps/api/tests/test_auth.py` must cover:
  - uniform password-reset request response for known/unknown emails;
  - expired and reused reset tokens;
  - email-change token success and reuse failure;
  - active session listing, single-session revoke, and revoke-others;
  - 2FA challenge flow and one-time recovery code.
- Full backend gate: `ruff check apps/api/app apps/api/tests apps/api/alembic` and
  `pytest apps/api/tests -q`.
- Migration gate: apply Alembic through the account-security revision on a fresh MySQL DB.

### 7. Wrong vs Correct

#### Wrong

```py
token = secrets.token_urlsafe(32)
UserSecurityToken(token_hash=token, purpose="password_reset")
```

#### Correct

```py
token = secrets.token_urlsafe(32)
UserSecurityToken(token_hash=self._hash_token(token), purpose="password_reset")
```

#### Wrong

```py
return await self._token_pair(user, request)  # before verifying TOTP
```

#### Correct

```py
return LoginResponse(two_factor_required=True, challenge_token=challenge)
```
