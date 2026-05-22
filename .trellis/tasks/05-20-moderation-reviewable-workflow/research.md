# Reviewable Workflow Research

## Relevant Specs

- `.trellis/spec/backend/moderation-admin-safety.md`: existing flag queue, hide/restore, audit, admin-only user status, content-safety block/mask contracts.
- `.trellis/spec/backend/spam-prevention-rate-limits.md`: screened rules and automatic spam actions are current auto-rule source; reviewables should reuse safe summaries and not leak private rule values.
- `.trellis/spec/backend/interactions-notifications.md`: review decisions and appeal state should notify affected users through unified notification jobs.
- `.trellis/spec/backend/background-jobs.md`: notification fan-out must use `BackgroundJobService.enqueue_notification(..., commit=False)`.
- `.trellis/spec/backend/database-guidelines.md`: any `reviewables`/`reviewable_events` migration needs table + column comments and indexes.
- `.trellis/spec/frontend/moderation-admin-safety.md`: existing `/admin/moderation` queue uses TanStack Query and feature-owned API functions.
- `.trellis/spec/frontend/notifications-interactions.md`: moderation notifications map to notification type `moderation` and route via topic/board data.
- `.trellis/spec/frontend/forum-api-wiring.md`: keep backend DTOs snake_case; feature API/composables own endpoint wiring.
- `.trellis/spec/guides/cross-layer-thinking-guide.md`: this spans DB -> service -> router -> frontend query/UI -> notifications.

## Code Patterns Found

- Existing flag workflow: `apps/api/app/models/moderation.py`, `apps/api/app/schemas/moderation.py`, `apps/api/app/services/moderation.py`, `apps/api/app/api/v1/moderation.py`.
  - `ModerationService.create_flag()` resolves a target snapshot, enforces spam limits, dedupes pending flags, writes `flags`, writes `audit_logs`, commits in service.
  - `ModerationService.list_flags()` scopes queues by global moderator/admin or `BoardMember.role in BOARD_MODERATOR_ROLES`.
- Existing content safety hooks: `apps/api/app/services/content_safety.py` and `ForumService.create_topic/reply_to_topic/update_post`.
  - Current actions are `block` and `mask`; reviewable task can add a `review` action that persists pending content instead of publishing immediately.
- Existing notifications: `apps/api/app/services/background_jobs.py`, `apps/api/app/workers/background_jobs.py`, `apps/api/app/models/interaction.py`.
  - Domain services enqueue notification jobs with `commit=False`; worker creates `notifications` and optional emails.
- Existing frontend moderation console: `apps/web/src/features/moderation/{api,model,queries}.ts` and `apps/web/src/pages/admin/ModerationPage.vue`.
  - Pages do not call raw fetch; mutations invalidate `queryKeys.moderationRoot`.
- Existing notification UI: `apps/web/src/features/notifications/model.ts`.
  - Unknown notification types fall back to `moderation`; URL builder prefers topic data then board slug.

## Proposed MVP Scope

1. Backend persisted reviewables:
   - Add `reviewables` table for unified review item state.
   - Add `reviewable_events` table for claim/release/decision/appeal audit trail.
   - Optional link fields: `flag_id`, `topic_id`, `post_id`, `board_id`, `created_by_id`, `assigned_to_id`, `resolved_by_id`.
2. Backend APIs under `/api/v1/moderation/reviewables`:
   - `GET /reviewables?status=&type=&limit=` moderator scoped queue.
   - `POST /reviewables/{id}/claim`, `/release`.
   - `POST /reviewables/{id}/decide` with action: `approve|reject|hide|delete|silence|escalate`.
   - `GET /reviewables/me` active user sees own reviewable summaries/appeal availability.
   - `POST /reviewables/{id}/appeal` owner/reporter creates an appeal event without exposing moderator-only details.
3. Integrate sources:
   - When `create_flag()` creates a new pending flag, also create/link a `reviewables` row of type `flag`.
   - Extend content safety with a review action for configured placeholder token in tests, returning `content_pending_review` and creating a `reviewable` row without publishing topic/post content.
4. Notifications/audit:
   - Every claim/release/decision/appeal writes `audit_logs` and `reviewable_events`.
   - Decisions/appeals enqueue `moderation` notifications to affected user(s), using topic/board route data when available.
5. Frontend:
   - Extend `features/moderation` DTOs/API/composables for reviewables.
   - Upgrade `/admin/moderation` from flag-only queue to tabs/sections for Reviewables + Flags/Audit.
   - Add user-facing appeal entry point where feasible (likely notification/detail summary first).

## Files Likely to Modify

### Backend

- `apps/api/app/models/moderation.py`: add `Reviewable`, `ReviewableEvent` models and literals.
- `apps/api/app/schemas/moderation.py`: request/response schemas for reviewables, decisions, appeals.
- `apps/api/app/services/moderation.py`: queue scoping, claim/release/decision, flag-to-reviewable integration, notifications.
- `apps/api/app/services/content_safety.py`: add pending-review result/action contract.
- `apps/api/app/services/forum.py`: intercept pending-review topic/reply/edit writes before publishing.
- `apps/api/app/api/v1/moderation.py`: add reviewable endpoints.
- `apps/api/app/db/schema_comments.py`: table/column comments.
- `apps/api/alembic/env.py` and new Alembic migration.
- `apps/api/tests/test_reviewables.py` and updates to `tests/test_content_safety.py`/`tests/test_moderation.py`.

### Frontend

- `apps/web/src/features/moderation/api.ts`
- `apps/web/src/features/moderation/model.ts`
- `apps/web/src/features/moderation/queries.ts`
- `apps/web/src/shared/api/queryKeys.ts`
- `apps/web/src/pages/admin/ModerationPage.vue`
- `apps/web/src/pages/admin/ModerationPage.scss`
- Possibly topic/detail components for user appeal entry point.

## Blocking Note

Current workspace contains uncommitted search-task leftovers touching moderation/search/migrations/tests. Do not implement reviewable code until those changes are committed, stashed, or explicitly approved to mix into this task.
