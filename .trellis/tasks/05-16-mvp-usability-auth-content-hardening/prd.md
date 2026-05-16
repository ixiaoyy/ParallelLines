# MVP Usability Auth and Content Hardening

## Goal

Turn the current technically complete forum MVP into a more genuinely usable product by closing high-friction gaps found after the first MVP pass: users need a real login/register path, visible current-user state, user profile pages, editable posts, working copy/link/quote actions, and a Playwright interaction audit across major pages.

## Requirements

### Backend

- Add public user profile endpoints for username profile and authored topics.
- Add post update endpoint with author/moderator/admin permission checks.
- Preserve existing API response and error shapes.
- Add tests for user profile reads and post edit permission boundaries.

### Frontend

- Add login/register UI and token/session handling based on `/auth/me`.
- Show current user in the topbar; allow logout without page reload.
- Add a user profile page with authored topic list.
- Make post edit, copy code, quote, copy link, and only-author filter actions functional enough for real browser use.
- Keep unauthenticated users guided to login rather than silently failing.

### Playwright / QA

- Extend smoke/interaction coverage beyond create-topic/reply to cover auth UI, profile navigation, copy/link buttons, edit flow, notification panel, moderation page permission state, and search/board navigation.
- Run local Playwright against a real API + Vite web server after implementation.

## Acceptance Criteria

- [x] A user can register/login from the UI, publish, reply, edit their own post, and logout.
- [x] `/u/:username` renders user identity and authored topics from API data.
- [x] Unauthorized users cannot edit another user's post.
- [x] Topic detail action buttons no longer include inert copy/link/filter/quote controls.
- [x] Playwright clicks through the primary navigation and verifies critical button behavior.
- [x] Backend ruff/tests and frontend lint/typecheck/build pass.
