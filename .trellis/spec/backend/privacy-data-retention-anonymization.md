# Backend Privacy, Retention, Anonymization, and Account Deletion Contract

## Scenario: user data export, anonymized deletion, and sensitive export/log redaction

### 1. Scope / Trigger

- Trigger: changing personal exports, admin user anonymization/deletion, self-service account
  deletion, privacy retention policy, or sensitive field redaction in exports/log-like admin data.
- Applies to `app/services/privacy.py`, `schemas/privacy.py`, `api/v1/users.py`,
  `api/v1/admin.py`, `services/backups.py`, user/profile services, upload/session/token models,
  and focused privacy tests.

### 2. Signatures

User APIs:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/users/me/export` | active user | Download own profile/content/action ZIP export. |
| `DELETE` | `/api/v1/users/me` | active user | Self-service account deletion: anonymize user and revoke private data. |
| `GET` | `/api/v1/users/privacy/retention` | public | Return current retention/deletion policy summary. |

Admin APIs:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/admin/users/{user_id}/anonymize` | admin | Anonymize a user without hard-deleting authored content. |
| `DELETE` | `/api/v1/admin/users/{user_id}` | admin | Admin account deletion; same privacy cleanup with `deleted` status. |

Request body for delete/anonymize is optional:

```json
{ "reason": "user requested erasure" }
```

`PrivacyActionResponse` fields:

- `user_id`, `username`, `email`, `status`, `anonymized`, `reason`.
- Cleanup counters: `revoked_sessions`, `deleted_security_tokens`, `deleted_recovery_codes`,
  `deleted_email_codes`, `deleted_drafts`, `deleted_notifications`,
  `removed_relationships`, `removed_board_memberships`, `removed_board_invitations`,
  `removed_private_message_participations`, `disabled_api_keys`, `disabled_webhooks`,
  `deleted_uploads`, `retained_uploads`, `anonymized_logs`.

### 3. Contracts

- Do not hard-delete the `users` row for forum authors. Preserve `topics.user_id` and
  `posts.user_id` so public topic reading keeps working.
- Anonymization sets non-identifying placeholders:
  - `username = anonymous-<stable user-id prefix>`;
  - `email = deleted-<stable user-id>@deleted.invalid`;
  - random non-login password hash;
  - profile text/avatar/URL/location removed;
  - role downgraded to `user`, level/trust/points reset, `status="deleted"`,
    `profile_visibility="private"`, `show_activity=false`, 2FA secret disabled.
- Deleted users cannot authenticate because `CurrentUserDep` requires `status="active"`.
- Admin cannot anonymize/delete self via admin routes; use self-service deletion instead.
- Cleanup must revoke sessions, delete security/recovery/email verification rows, delete drafts,
  delete personal notifications, remove follow/ignore/block relationships, remove board membership
  and private-message participant rows, disable owned API keys/webhooks, and disable email prefs.
- Avatar and temporary uploads are deleted from local storage when possible; attached post uploads
  are retained so topics remain readable, but owner filename metadata is anonymized.
- Public user profile lookup must not expose `status="deleted"` users.
- Site/user exports must redact password/token/secret/code fields and sensitive hashes such as
  `hashed_password`, `token_hash`, `refresh_token_hash`, `code_hash`, and `idempotency_key`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Non-admin calls admin anonymize/delete | `403 admin_required` |
| Admin anonymizes/deletes self via admin route | `422 cannot_anonymize_self` / `cannot_delete_self` |
| Unknown target user | `404 user_not_found` |
| Anonymized user uses old access token | `401 invalid_token` |
| Public reads old username profile | `404 user_not_found` |
| Public reads pre-existing public topic after deletion | `200`; author name is anonymous placeholder |
| Export contains token/hash/secret fields | Values are absent or `***redacted***` |

### 5. Good/Base/Bad Cases

- Good: admin anonymizes Alice; Alice's old email/username disappear, sessions are revoked, and
  Alice's public topic still renders with `anonymous-...` author.
- Base: user self-deletes; the same anonymization cleanup runs and future requests using the old
  bearer token fail.
- Bad: hard-deleting `users` and cascading `topics/posts`, breaking topic reads.
- Bad: keeping attached uploads readable but retaining the original private filename.
- Bad: site export includes `background_jobs.idempotency_key` for password-reset jobs.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `ruff check app/services/privacy.py app/schemas/privacy.py app/api/v1/users.py app/api/v1/admin.py app/services/backups.py app/services/users.py tests/test_privacy_data_retention.py`
- `pytest tests/test_privacy_data_retention.py -q`
- Focus assertions:
  - anonymization changes username/email and sets status `deleted`;
  - sessions are revoked and old token cannot export;
  - old username profile is hidden;
  - public topic read remains `200` and shows anonymous author;
  - site/user exports do not contain raw token hashes, job secrets, or idempotency hashes.

### 7. Wrong vs Correct

#### Wrong

```python
await session.delete(user)  # cascades or breaks authored content relations
```

#### Correct

```python
user.username = anonymous_username_for(user.id)
user.email = anonymous_email_for(user.id)
user.status = "deleted"
user.profile_visibility = "private"
```
