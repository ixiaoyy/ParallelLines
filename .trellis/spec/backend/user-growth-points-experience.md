# Backend User Growth, Points, and Experience Contract

## Scope

Applies to user growth fields, reward rules, level calculation, audit ledger rows, and admin adjustments.

## Data Model

- `users.points_balance`: current spendable/adjustable points balance, never below `0`.
- `users.experience_total`: cumulative experience used to derive `users.level`, never below `0`.
- `users.level`: stored display cache derived by `app.core.growth.level_for_experience()` after any experience change.
- `user_point_events`: append-only audit ledger with `user_id`, `source_type`, `source_id`,
  `points_delta`, `experience_delta`, `balance_after`, `experience_after`, `level_after`,
  `actor_id`, `idempotency_key`, and `note`.

## Level Rule

Keep thresholds centralized in `app.core.growth.LEVEL_THRESHOLDS`:

```python
(0, 50, 150, 300, 600, 1000, 1600, 2400, 3400, 4600, 6000)
```

Use `level_for_experience()`, `experience_to_next_level()`, and `level_progress_percent()` for
all backend DTO fields. UI must not duplicate the threshold table.

## Reward Sources

All writes go through `GrowthService`; routers and feature services must not mutate growth fields directly.

| Source | Points | XP | Guard |
|---|---:|---:|---|
| `email_verified` | 20 | 20 | one event per user |
| `topic_created` | 5 | 15 | daily cap 25 points / 75 XP |
| `post_created` | 2 | 8 | daily cap 20 points / 80 XP; public topic replies only |
| `content_liked` | 1 | 4 | daily cap 20 points / 80 XP; no self-like reward |
| `invite_accepted_inviter` | 10 | 25 | daily cap 50 points / 125 XP |
| `invite_accepted_invitee` | 5 | 10 | daily cap 25 points / 50 XP |
| `admin_adjustment` | variable | variable | admin-only, no cap, ledger note recommended |

## API Contracts

- `UserPublic`, `UserProfileResponse`, and `AdminUserResponse` include:
  - `level`
  - `points_balance`
  - `experience_total`
  - `experience_to_next_level`
  - `level_progress_percent`
- `TopicResponse` and `PostResponse` include `author_level` for author cards.
- `AdminUserUpdateRequest` may include `points_delta`, `experience_delta`, and
  `adjustment_reason`; negative deltas are floored at `0` balance/experience.

## Migration and Consistency

- New users default to `points_balance=0`, `experience_total=0`, `level=0`.
- Migrations must backfill existing `experience_total` from any non-zero stored `level` threshold
  so existing display levels are not silently downgraded.
- Experience changes recompute `users.level`; manual level edits are legacy/admin metadata and can be
  overwritten by the next experience-changing event.

## Tests Required

During normal roadmap development use downgraded testing:

- `ruff check app tests alembic`
- Focused growth test covering defaults, at least one behavior reward, idempotent like reward, and level boundaries.
- Broaden to daily-cap/admin-adjustment matrices only when explicitly requested or before release/commit hardening.
