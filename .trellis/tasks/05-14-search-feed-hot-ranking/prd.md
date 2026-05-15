# PRD: Search Feed and Hot Ranking

## Goal

Make content discoverable through search, feeds, and ranking.

## Scope

- Latest/top/hot topic feed APIs.
- Board-scoped and tag-scoped topic lists.
- Database-native full-text search over topic title and post raw markdown.
- Hot score background job with deterministic formula.
- Frontend search page, hot list, tag filter, and empty states.

## Acceptance Criteria

- Public topic lists support cursor pagination.
- Search supports query, board, tag, and author filters.
- Hot ranking can be recomputed idempotently.
- Feed ordering is covered by tests.
- UI exposes `最新`, `热门`, `精华/Top`, and search routes.

## Progress

- [x] Latest/top/hot topic feed API accepts query, board, tag, author, cursor, and limit.
- [x] `/api/v1/search` searches topic title and post raw Markdown with filter support.
- [x] Hot score recompute worker is idempotent and covered by tests.
- [x] Frontend search route and topbar search are wired to the search API with fixture fallback.
