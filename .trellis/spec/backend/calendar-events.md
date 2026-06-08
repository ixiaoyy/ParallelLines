# Calendar Events Contract

## Scenario: Community events, RSVP, local time metadata, and iCal feed

### 1. Scope / Trigger

- Trigger: changing community calendar events, RSVP/capacity, reminder metadata, or iCal output.
- Applies to `models/event.py`, `schemas/events.py`, `services/events.py`, `api/v1/events.py`,
  and event migrations.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/events?start_at=&end_at=` | optional | Lists events in a date window. |
| `POST /api/v1/events` | user | Creates a community event. |
| `PUT /api/v1/events/{event_id}/lifecycle` | creator / global moderator | Sets event status `scheduled` or `canceled`. |
| `DELETE /api/v1/events/{event_id}` | creator / global moderator | Deletes an event and cascades RSVP rows. |
| `PUT /api/v1/events/{event_id}/rsvp` | user | Sets RSVP status `going` or `canceled`. |
| `GET /api/v1/events/calendar.ics` | public | Returns iCal feed for calendar subscription. |

### 3. Contracts

- Event times are stored as timezone-aware UTC datetimes; `timezone` stores the IANA display zone
  preferred by the event creator.
- `end_at` must be after `start_at`.
- `rsvp_deadline`, when set, must be before `start_at`.
- RSVP `going` is blocked after `rsvp_deadline` or event start.
- RSVP `going` is blocked when event `status` is `canceled`.
- Event creators, admins, and global moderators can set status to `canceled`/`scheduled` or delete the event.
- RSVP `going` respects `capacity`; canceled RSVPs do not count toward capacity.
- iCal output must escape title/description text, use UTC `DTSTART`/`DTEND`, and emit `STATUS:CANCELLED` for canceled events.
- `reminder_minutes_before` and `EventRsvp.reminder_sent_at` are persisted for future worker-based
  reminder jobs; reminders should use user locale/timezone when worker delivery is implemented.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| End before start | `event_invalid_time_range` / 422 |
| Deadline after start | `event_invalid_rsvp_deadline` / 422 |
| RSVP after deadline/start | `event_rsvp_closed` / 422 |
| RSVP after event canceled | `event_canceled` / 422 |
| Capacity reached | `event_capacity_full` / 422 |
| Missing event id | `event_not_found` / 404 |
| Non-creator/non-moderator manages event | `permission_denied` / 403 |
| iCal feed | `text/calendar` response with one `VEVENT` per event |

### 5. Good/Base/Bad Cases

- Good: user creates event with `Asia/Shanghai`, clients display local time while iCal stays UTC.
- Base: first user RSVPs to capacity-1 event, second user receives capacity error.
- Base: admin cancels an event, the list keeps it with `status=canceled`, RSVP is blocked, and iCal marks it canceled.
- Base: admin deletes an event, subsequent lists and iCal no longer include it.
- Bad: using browser-local times as backend source of truth without timezone metadata.
- Bad: generating iCal with unescaped commas/newlines.

### 6. Tests Required

- Default roadmap smoke: `pytest tests/test_events.py -q`.
- Assertions: event creation/listing, RSVP capacity, deadline guard, and iCal feed.
- Run `ruff check` on touched event model/schema/service/router/migration/test files.

### 7. Wrong vs Correct

#### Wrong

```python
event.start_at = datetime.fromisoformat(payload.local_time)
```

#### Correct

```python
start_at = EventService(session)._aware(payload.start_at)
```

Persist a timezone-aware instant plus separate display timezone metadata.
