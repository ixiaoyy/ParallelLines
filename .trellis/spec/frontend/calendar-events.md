# Calendar Events UI Contract

## Scenario: Calendar page, RSVP actions, and local time display

### 1. Scope / Trigger

- Trigger: changing event list views, event creation forms, RSVP buttons, local time formatting, or
  iCal subscription links.
- Applies to `features/events/`, `pages/events/`, `app/router.ts`, `AppShell.vue`, and query keys.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Purpose |
|---|---|
| `fetchEvents(params)` | Load calendar events |
| `createEvent(payload)` | Create event |
| `rsvpEvent(eventId, payload)` | RSVP going/canceled |
| `useEvents()` | Query wrapper |
| `useCreateEvent()` | Mutation + event invalidation |
| `useRsvpEvent()` | Mutation + event invalidation |

Route:

- `/events` → `EventsPage.vue`

### 3. Contracts

- Event DTOs come from generated OpenAPI types.
- Local time display uses `Intl.DateTimeFormat` with `event.timezone`.
- Event creation uses `datetime-local` input converted to ISO instant before sending.
- RSVP buttons are shown only to authenticated users.
- iCal subscription link points to `/api/v1/events/calendar.ics`.
- Empty/loading/error states must be visible.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Anonymous views events | Can read list and iCal link, cannot RSVP/create |
| Auth user creates event | Event query invalidates and new event appears |
| RSVP succeeds | Event query invalidates and `my_rsvp_status` refreshes |
| RSVP fails due deadline/capacity | Mutation surfaces API error; no local fake success |
| Browser timezone exists | Form defaults to local IANA timezone |

### 5. Good/Base/Bad Cases

- Good: card shows `Asia/Shanghai` event using that timezone even for users elsewhere.
- Base: user creates a small event, another user RSVPs, count updates after refetch.
- Bad: hardcoding all event display to browser local time without showing event timezone.

### 6. Tests Required

- Default roadmap scope: `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web lint`.
- OpenAPI changes must also pass `pnpm --dir apps/web openapi:check`.
- Browser/e2e calendar tests are deferred unless requested.

### 7. Wrong vs Correct

#### Wrong

```ts
new Date(event.start_at).toLocaleString()
```

#### Correct

```ts
new Intl.DateTimeFormat("zh-CN", { timeZone: event.timezone }).format(new Date(event.start_at));
```

Use event timezone metadata for consistent local-date rendering.
