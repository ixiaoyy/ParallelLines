# Frontend Email Preferences Contract

## Scenario: Authenticated user controls forum email delivery

### 1. Scope / Trigger

- Trigger: changing `/email-preferences`, email preference API wiring, notification email toggles, or digest frequency UI.
- Applies to `features/email-preferences/`, `pages/email/EmailPreferencesPage.vue`, router entries, app-shell navigation, and shared query keys.

### 2. Signatures

Routes and API:

| Item | Contract |
|---|---|
| `/email-preferences` | Authenticated preference page; unauthenticated users see a login CTA |
| `fetchEmailPreferences()` | `GET /email/preferences` |
| `updateEmailPreferences(payload)` | `PUT /email/preferences` |
| `queryKeys.emailPreferences` | TanStack Query key for preference server state |

Payload fields:

- `email_enabled`
- `notify_replied`
- `notify_mentioned`
- `notify_liked`
- `notify_topic_new_post`
- `notify_board_new_topic`
- `digest_frequency: "off" | "daily" | "weekly"`

### 3. Contracts

- The page uses `/auth/me` via `useCurrentUser`; it must not infer identity from JWT content.
- Preference state comes from TanStack Query, with a local draft copy for editing.
- Saving sends only the documented preference fields and replaces the query cache with the server response.
- The master switch disables UI controls visually but still preserves individual toggle values for later re-enable.
- The app shell shows the Mail navigation entry only to authenticated users.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No access token | Page shows login CTA and does not call save mutation |
| Query loading | Page shows a lightweight loading card |
| Save success | Success notice appears and cache updates |
| Invalid/expired token | Error copy asks user to log in again |
| `delivery_status` not ok | Status and disabled reason are visible on the master card |

### 5. Good/Base/Bad Cases

- Good: user disables replied emails, keeps mentions on, selects weekly digest, and saves once.
- Base: user lands unauthenticated from `/email-preferences` and can go to `/auth?redirect=/email-preferences`.
- Bad: mirroring preference state in Pinia or localStorage instead of TanStack Query.

### 6. Tests Required

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- Browser/static verification should confirm `/email-preferences` renders the hero and unauthenticated login CTA.

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
