# Backend User Growth, Points, and Experience Contract

## Scope

Applies to user growth fields, reward rules, level calculation, audit ledger rows, and admin adjustments.

## Data Model

- `users.points_balance`: current spendable/adjustable points balance, never below `0`. This is the
  user-facing usable points balance for future redemption/unlock flows, so spending may decrease it.
- `users.experience_total`: cumulative growth value used to derive normal auto-promoted levels, never
  below `0`. This is not spendable and must not be reduced by points redemption/unlock flows.
- `users.level`: stored display level cache. Normal growth-value changes use
  `app.core.growth.level_for_experience()` and caps at Lv.4; Lv.5 is the review-only maximum and can
  only be assigned by admin moderation.
- `user_point_events`: append-only audit ledger with `user_id`, `source_type`, `source_id`,
  `points_delta`, `experience_delta`, `balance_after`, `experience_after`, `level_after`,
  `actor_id`, `idempotency_key`, and `note`.

## Level Rule

Keep thresholds centralized in `app.core.growth.LEVEL_THRESHOLDS`:

```python
(0, 50, 150, 300, 600)
```

Use `level_for_experience()`, `experience_to_next_level()`, and `level_progress_percent()` for
all backend DTO fields. UI must not duplicate the threshold table. `level_for_experience()` never
returns the review-only maximum Lv.5; growth writes preserve an existing admin-reviewed Lv.5 instead
of downgrading it.

## Reward Sources

All writes go through `GrowthService`; routers and feature services must not mutate growth fields directly.

| Source | Usable points | Growth value | Guard |
|---|---:|---:|---|
| `email_verified` | 20 | 20 | one event per user |
| `daily_login` | 5 | 5 | once per UTC day; awarded after successful password/2FA login |
| `topic_created` | 5 | 5 | daily cap 25 usable points / 25 growth |
| `post_created` | 1 | 1 | daily cap 20 usable points / 80 growth; public topic replies only |
| `content_liked` | 1 | 1 | daily cap 20 usable points / 20 growth; no self-like reward; idempotent per actor and target |
| `content_bookmarked` | 1 | 1 | daily cap 20 usable points / 20 growth; no self-bookmark reward; first bookmark only |
| `topic_replied` | 1 | 1 | daily cap 20 usable points / 20 growth; public topic receives a non-author reply |
| `invite_accepted_inviter` | 10 | 10 | daily cap 50 usable points / 50 growth |
| `invite_accepted_invitee` | 5 | 5 | daily cap 25 usable points / 25 growth |
| `admin_adjustment` | variable | variable | admin-only, no cap, ledger note recommended |

User-facing copy should call `points_balance` "可用积分" and `experience_total` "成长值". Avoid
showing the English term "XP" in normal user surfaces.

## API Contracts

- `UserPublic`, `UserProfileResponse`, and `AdminUserResponse` include:
  - `level`
  - `points_balance`
  - `experience_total`
  - `experience_to_next_level`
  - `level_progress_percent`
- `TopicResponse` and `PostResponse` include `author_level` for author cards.
- `AdminUserUpdateRequest` may include `level` (0–5), `points_delta`, `experience_delta`, and
  `adjustment_reason`; negative deltas are floored at `0` usable points/growth value. Lv.5 is
  review-only and must only be set through admin update paths.

## Migration and Consistency

- New users default to `points_balance=0`, `experience_total=0`, `level=0`.
- Migrations must backfill existing `experience_total` from any non-zero stored `level` threshold
  so existing display levels are not silently downgraded.
- Growth-value changes recompute `users.level` up to Lv.4. If a user already has admin-reviewed Lv.5,
  later growth events preserve Lv.5 until an admin lowers it.

## Tests Required

During normal roadmap development use downgraded testing:

- `ruff check app tests alembic`
- Focused growth test covering defaults, at least one behavior reward, idempotent like reward, and level boundaries.
- Broaden to daily-cap/admin-adjustment matrices only when explicitly requested or before release/commit hardening.
