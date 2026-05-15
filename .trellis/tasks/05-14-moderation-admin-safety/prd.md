# PRD: Moderation Admin and Safety

## Goal

Provide minimal but reliable community governance for boards and posts.

## Scope

- Role permissions: user, board_moderator, board_owner, admin.
- Report/flag flow for topics and posts.
- Moderator queue and status transitions.
- Soft hide/restore topic/post.
- User silence/suspend basics.
- Audit log for all moderation actions.
- Frontend moderation panel and admin views.

## Acceptance Criteria

- [x] Unauthorized users cannot moderate content.
- [x] Moderation actions write audit logs.
- [x] Hidden content is not visible in public lists but can be inspected by moderators.
- [x] Report queue supports pending/resolved/rejected states.
- [x] Tests cover permission boundaries.

## Progress

- [x] Added `flags` and `audit_logs` models/migration plus moderation schemas.
- [x] Added moderation service/router for flag creation, queue, status transitions, hide/restore, audit logs, and admin user status updates.
- [x] Added backend tests for permission boundaries, hidden content visibility, user status admin controls, and audit log writes.
- [x] Added frontend report actions and `/admin/moderation` console with queue, hide/restore, flag resolution, user status form, and audit panel.
- [x] Updated backend/frontend code-specs for moderation contracts.
