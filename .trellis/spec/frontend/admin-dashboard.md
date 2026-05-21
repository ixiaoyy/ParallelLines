# Frontend Admin Dashboard Contract

## Scenario: Operational admin dashboard and public site settings

### 1. Scope / Trigger

- Trigger: wiring admin-only operational UI, public site settings, user management,
  system health, mail logs, or audit logs.
- Applies to `features/admin/`, `pages/admin/AdminDashboardPage.vue`, router,
  `AppShell.vue`, and admin navigation.

### 2. Signatures

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `fetchPublicSiteSettings()` | `GET /api/v1/site/settings` | `PublicSiteSettingsResponse` |
| `fetchAdminSettings()` | `GET /api/v1/admin/settings` | `SiteSettingResponse[]` |
| `updateAdminSetting(key, payload)` | `PUT /api/v1/admin/settings/{key}` | `SiteSettingResponse` |
| `fetchAdminUsers(params)` | `GET /api/v1/admin/users?...` | `AdminUserResponse[]` |
| `updateAdminUser(userId, payload)` | `PUT /api/v1/admin/users/{id}` | `AdminUserResponse` |
| `fetchAdminSystem()` | `GET /api/v1/admin/system` | `AdminSystemOverviewResponse` |

Query composables:

- `usePublicSiteSettings()`
- `useAdminSettings()`
- `useUpdateAdminSetting()`
- `useAdminUsers(params)`
- `useUpdateAdminUser()`
- `useAdminSystem()`

Routes:

- `/admin` → admin dashboard.
- `/admin/moderation` → existing moderation queue.

### 3. Contracts

- Public settings belong in TanStack Query under `queryKeys.siteSettingsPublic`;
  app shell may use only public keys such as `site_title` and `site_tagline`.
- Admin routes must show explicit login/permission states. Do not render an empty
  dashboard when the backend returns 403.
- Admin navigation must distinguish admin dashboard access from moderation access:
  admins see 后台, moderators may still see 审核.
- DTOs stay snake_case at the API boundary. UI helpers may map labels for roles,
  statuses, and setting categories.
- Setting forms must preserve type:
  - boolean uses checkbox and sends bool;
  - integer uses number input and sends number;
  - string sends trimmed/editable string.
- Mutations invalidate `queryKeys.adminRoot`; setting mutations also invalidate
  `queryKeys.siteSettingsPublic` so public branding refreshes.
- User management changes role/status/level together through `updateAdminUser`;
  pages must not infer admin powers from `level`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No token visits `/admin` | Login-required card is shown |
| Moderator visits `/admin` | Permission card is shown, not a fake empty dashboard |
| Admin updates `site_title` | Public settings query invalidates and app shell title updates |
| Backend returns cache degraded in system overview | Dashboard shows degraded badge, not a hard failure |
| User list is empty for filters | User detail is not submitted without a selected user |
| Setting save is pending | Save buttons are disabled to prevent duplicate writes |

### 5. Good/Base/Bad Cases

- Good: `AppShell.vue` reads `usePublicSiteSettings()` and falls back to checked-in
  Chinese defaults if the public settings API fails.
- Base: admin opens `/admin`, sees system counters, edits a setting, selects a user,
  changes role/status/level, then confirms audit timeline updated after refetch.
- Bad: admin page imports `apiPut` directly instead of using `features/admin/api.ts`.
- Bad: public settings query is stored in Pinia and drifts from backend state.

### 6. Tests Required

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- Backend `tests/test_admin.py` remains source of truth for permission, audit,
  setting-type, registration-gate, and system-panel contracts.

### 7. Wrong vs Correct

#### Wrong

```ts
await apiPut(`/admin/settings/${key}`, { value: input.value });
```

#### Correct

```ts
updateSettingMutation.mutate({ key, payload: { value: typedSettingValue } });
```
