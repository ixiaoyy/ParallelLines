# Frontend Email Preferences Contract

## Scenario: Authenticated user controls forum email delivery

### 1. Scope / Trigger

- Trigger: changing `/account/preferences`, the legacy `/email-preferences` redirect, email preference API wiring, notification email toggles, or digest frequency UI.
- Applies to `features/email-preferences/`, `pages/email/EmailPreferencesPage.vue`, router entries, app-shell navigation, and shared query keys.

### 2. Signatures

Routes and API:

| Item | Contract |
|---|---|
| `/account/preferences` | Authenticated preference page; unauthenticated users see a login CTA |
| `/email-preferences` | Legacy redirect to `/account/preferences` |
| `fetchEmailPreferences()` | `GET /email/preferences` |
| `updateEmailPreferences(payload)` | `PUT /email/preferences` |
| `queryKeys.emailPreferences` | TanStack Query key for preference server state |

Payload fields:

- `email_enabled`
- `notify_replied`
- `notify_mentioned`
- `notify_liked`
- `notify_topic_new_post`
- `digest_frequency: "off" | "daily" | "weekly"`
- `quiet_hours_start: number | null` (UTC hour `0..23`)
- `quiet_hours_end: number | null` (UTC hour `0..23`)

### 3. Contracts

- The page uses `/auth/me` via `useCurrentUser`; it must not infer identity from JWT content.
- Preference state comes from TanStack Query, with a local draft copy for editing.
- Saving sends only the documented visible preference fields plus `notify_board_new_topic=false` for
  legacy cleanup, then replaces the query cache with the server response.
- The UI must not render a "board new topic" email toggle; board-level subscriptions are retired.
- The master switch disables UI controls visually but still preserves individual toggle values for later re-enable.
- Quiet hours are edited as UTC hour selects. Enabling quiet hours should default to a practical
  overnight window (for example `22 -> 7`); disabling sends `quiet_hours_start=null` and
  `quiet_hours_end=null` so the backend stops suppressing immediate emails.
- The quiet-hours controls disable visually when the master `email_enabled` switch is off, but they
  preserve the user's start/end values for later re-enable.
- The app shell shows the Mail navigation entry only to authenticated users.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No access token | Page shows login CTA and does not call save mutation |
| Query loading | Page shows a lightweight loading card |
| Save success | Success notice appears and cache updates |
| Invalid/expired token | Error copy asks user to log in again |
| `delivery_status` not ok | Status and disabled reason are visible on the master card |
| Quiet hours disabled | Save payload includes `quiet_hours_start=null` and `quiet_hours_end=null` |
| Quiet hours enabled | Save payload includes integer UTC hours in `0..23` |

### 5. Good/Base/Bad Cases

- Good: user disables replied emails, keeps mentions on, selects weekly digest, and saves once.
- Good: user enables quiet hours from 22:00 UTC to 07:00 UTC; the page sends both hour fields and
  preserves all per-event toggles.
- Base: user lands unauthenticated from `/account/preferences` and can go to `/auth?redirect=/account/preferences`.
- Bad: mirroring preference state in Pinia or localStorage instead of TanStack Query.

### 6. Tests Required

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- Browser/static verification should confirm `/account/preferences` renders the hero and unauthenticated login CTA.
- Browser/static verification should confirm quiet-hours controls render, can be enabled/disabled,
  and do not clear event toggles before save.

### 7. Wrong vs Correct

#### Wrong

```ts
localStorage.setItem("email_enabled", String(enabled));
```

#### Correct

```ts
const saved = await updateEmailPreferencesMutation.mutateAsync({ email_enabled: enabled });
queryClient.setQueryData(queryKeys.emailPreferences, saved);
```
