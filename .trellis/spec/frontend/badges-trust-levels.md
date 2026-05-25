# Badges and Trust Levels UI

## Scenario: Rendering trust and badge state

### 1. Scope / Trigger
- Trigger: when API DTOs add trust/badge fields or the admin UI manages user badges.
- UI must present trust as risk/participation status, not as staff permission.

### 2. Signatures
- Types:
  - `features/badges/model.ts`: `BadgeResponse`, `UserBadgeResponse`, `BadgeGrantRequest`, `BadgeRevokeRequest`.
  - `UserPublic`, `UserProfile`, `AdminUserResponse`: `trust_level`, `trust_level_label`.
  - `TopicResponse`/`PostResponse`: `author_trust_level`, `author_trust_level_label` mapped into VMs.
- Queries/mutations:
  - `useAdminBadges()` -> `GET /admin/badges`
  - `useGrantAdminUserBadge()` -> `POST /admin/users/{id}/badges`
  - `useRevokeAdminUserBadge()` -> `POST /admin/users/{id}/badges/{slug}/revoke`

### 3. Contracts
- Profile hero shows role, display level, trust level, and active badge chips.
- Topic and post author metadata show `Lv.x` plus `TLy label`.
- Admin user detail shows trust separately from role, lists active badges, and provides grant/revoke controls.
- Admin badge mutations invalidate `queryKeys.adminRoot` so user lists refresh.

### 4. Validation & Error Matrix
| Case | UI behavior |
|---|---|
| Empty `badges` | Show an empty state, not a broken chip list |
| Badge catalog load failure | Show admin panel error text |
| Grant disabled | Disable when no badge slug or mutation pending |
| Revoke reason empty | Send default manual revoke reason |

### 5. Good/Base/Bad Cases
- Good: `TL2 · 常驻成员` appears as a chip near the existing level display.
- Base: users with no badges still render profile and admin detail normally.
- Bad: do not hide/show admin controls based on trust level; use role/session permissions from backend.

### 6. Tests Required
- Typecheck must cover DTO/VM mappings.
- Lint must cover Vue templates and imports.
- Detailed browser automation is optional under downgraded testing unless requested.

### 7. Wrong vs Correct
#### Wrong
```ts
const canModerate = user.trust_level >= 3;
```

#### Correct
```ts
const canModerate = user.role === "admin" || user.role === "moderator";
const trustLabel = `TL${user.trust_level} · ${user.trust_level_label}`;
```
