# Real Data Website Hardening

## Goal

Stop treating 平行线 as a stitched static demo. Make the visible forum experience rely on real API data whenever a backend is configured, remove runtime mock fallbacks from production query paths, and surface honest loading/error/empty states instead of silently replacing failures with fixtures.

## Requirements

### Frontend

- Remove `mockForum` runtime fallback from board/topic/post query composables.
- Replace mock-derived related topics, board detail preview, and tag/sidebar data with API-derived data or route/query utility code.
- Keep static design/sample data only in clearly named demo/design-system fixtures, not in production forum data paths.
- Add visible error/empty states when API data is unavailable; do not pretend data exists.
- Keep the recently implemented auth/profile/post action flows working with real API data.

### Backend / API

- Reuse existing APIs where possible: boards, board detail, board topics, topics, posts, search, user profile.
- Add focused API support only if a visible production page cannot be backed by existing endpoints.
- Preserve response envelopes and error shapes.

### QA

- Extend Playwright smoke to assert real API-backed data after page reloads and detect mock fallback regressions.
- Run real API + Vite + Playwright after implementation.

## Acceptance Criteria

- [x] `apps/web/src/shared/api/mockForum.ts` is not imported by production pages/features except for intentionally isolated demo/design fixture modules.
- [x] Board directory, board detail, topic detail, search, home, and user profile use API data without silent mock fallback.
- [x] API failures render visible error or empty states instead of fake boards/topics/posts.
- [x] Playwright validates key user flows against real API data and includes a regression check that created content remains after reload/search/profile navigation.
- [x] Frontend lint/typecheck/build and API ruff/pytest pass.

## Technical Notes

- This task continues on top of the current uncommitted MVP auth/content hardening changes.
- Prefer small API adapters and route utility extraction over broad rewrites.
- If a mock is needed for design-system screenshots, move/name it as fixture-only and keep it out of API query composables.

## Verification

- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web build`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 PLAYWRIGHT_API_BASE_URL=http://127.0.0.1:8001/api/v1 pnpm --dir apps/web test:smoke`
- `apps/api/.venv/Scripts/ruff.exe check app tests`
- `apps/api/.venv/Scripts/pytest.exe -q`
- `git diff --check`
- Runtime mock audit: `rg "mockForum|mockNotifications|mockBoards|mockTopics|getPostsByTopicId|getRelatedTopics|getBoardBySlug|createMockNotificationList|home/fixtures" apps/web/src apps/web/tests apps/api/app apps/api/tests -n` returned no matches.
