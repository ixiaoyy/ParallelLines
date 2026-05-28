# Badges and Trust Levels

## Scenario: Badges and trust levels on top of growth

### 1. Scope / Trigger
- Trigger: when adding behavior-based badges, trust-level risk controls, or admin badge operations.
- Trust level is a risk-control signal, not a permission role. Never check `trust_level` to grant admin/moderator authority.

### 2. Signatures
- DB:
  - `users.trust_level:int default 0`
  - `users.trust_level_changed_at:datetime|null`
  - `badge_definitions(slug unique, name, description, category, icon, trust_level_required, active)`
  - `user_badges(user_id, badge_id, source_type, source_id, granted_by_id, revoked_at, revoked_by_id, revoke_reason, idempotency_key unique, note)`
  - `user_trust_level_events(user_id, previous_level, next_level, source_type, source_id, actor_id, note)`
- Service:
  - `BadgeTrustService.grant_badge(user_id, badge_slug, source_type, source_id?, actor_id?, note?, idempotency_key?)`
  - `BadgeTrustService.recompute_trust(user, source_type, source_id?, actor_id?, note?)`
  - `trust_adjusted_limit(base_limit, trust_level)`
- Admin API:
  - `GET /api/v1/admin/badges`
  - `POST /api/v1/admin/users/{user_id}/badges { badge_slug, note? }`
  - `POST /api/v1/admin/users/{user_id}/badges/{badge_slug}/revoke { reason? }`

### 3. Contracts
- `UserPublic`, `UserProfileResponse`, and `AdminUserResponse` include `trust_level` and `trust_level_label`.
- Public profile and admin user payloads include active `badges: UserBadgeResponse[]`.
- Topic/post responses include `author_trust_level` and `author_trust_level_label`.
- Auto badges use stable idempotency keys, e.g. `badge:verified-member:{user_id}`.
- Default trust rules: TL1 at verified/20 growth value, TL2 at 150 growth value + public topic/reply participation, TL3 at 600 growth value + stronger participation/likes; TL4 is preserved for manual/core users and is not auto-granted.

### 4. Validation & Error Matrix
| Case | Behavior |
|---|---|
| Unknown badge slug | `badge_not_found` |
| Revoke inactive/missing user badge | `user_badge_not_found` |
| Non-admin badge management | `admin_required` |
| Low-trust link flood | new-user screening still blocks/silences using `trust_level == 0` |
| Rate limits | user-scoped write limits use `trust_adjusted_limit`; IP/account limits stay unchanged |

### 5. Good/Base/Bad Cases
- Good: email verification grants `verified-member`, awards growth value, recomputes TL1, and writes a trust event.
- Good: first public topic/reply/received-like grants behavior badge once even if the action is retried.
- Base: TL1 users keep default write limits.
- Bad: do not infer admin/moderator rights from TL3/TL4.

### 6. Tests Required
- Boundary unit: `trust_adjusted_limit(5, 0) == 3`, TL1 unchanged, TL2/TL3 expanded.
- API smoke: verification returns TL1 and profile includes `verified-member`.
- Admin smoke: admin can grant and revoke an active badge.
- Run detailed matrix only when explicitly requested or when changing schema/security-critical behavior.

### 7. Wrong vs Correct
#### Wrong
```python
if current_user.trust_level >= 3:
    allow_admin_action()
```

#### Correct
```python
if not is_admin(current_user):
    raise PermissionDeniedError("admin_required", "Admin role required")
limit = trust_adjusted_limit(policy.limit, current_user.trust_level)
```
