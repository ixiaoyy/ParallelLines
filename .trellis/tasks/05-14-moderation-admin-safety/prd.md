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

- Unauthorized users cannot moderate content.
- Moderation actions write audit logs.
- Hidden content is not visible in public lists but can be inspected by moderators.
- Report queue supports pending/resolved/rejected states.
- Tests cover permission boundaries.
