# Project Structure Scalability PRD

## Goal

Plan a safer project structure for ParallelLines so future backend APIs, frontend screens, plugins, and background capabilities can grow without turning routers, services, pages, or shared utilities into catch-all files.

## Known Facts

- The repo is a two-app workspace with `apps/api` and `apps/web`.
- Backend specs already define the target layers: `api/v1`, `core`, `db`, `models`, `schemas`, `services`, `repositories`, `workers`, and domain-mirrored tests.
- The current backend has routers, services, models, schemas, and workers, but no `app/repositories` directory yet.
- `apps/api/app/services/forum.py` is already a broad domain service handling boards, topics, posts, polls, lifecycle, moderation-adjacent reads, notifications, tags, and private-message behavior.
- Frontend already follows `app`, `pages`, `features`, `entities`, and `shared`.
- Frontend domain folders are numerous enough that cross-feature import rules and ownership boundaries matter more than another top-level folder.
- Current task context includes backend and frontend directory-structure specs plus the code-reuse guide.

## Assumptions

- Near-term work should be incremental. A large directory move with no feature value is too risky while product behavior is still changing.
- API response shapes and route paths should remain stable unless a separate API-contract task explicitly changes them.
- Frontend styles should remain stable during structural migration; structure changes should not rewrite visual design.

## Open Questions

- Should the first implementation task focus on backend query/repository extraction, frontend feature ownership cleanup, or test organization?
- Should architectural boundaries be enforced by lint rules now, or only documented first and enforced later?

## Requirements

- Keep `apps/api/app/api/v1` routers thin: request parsing, auth dependency use, service call, response model only.
- Move reusable complex SQL and pagination/filter fragments into `apps/api/app/repositories`.
- Keep service methods responsible for transactions and cross-aggregate side effects.
- Split oversized service files by domain only when there is a clear public service boundary and focused tests.
- Keep SQLAlchemy models behavior-light; no business-heavy model methods.
- Keep frontend route-level code in `pages`; reusable feature UI and query hooks belong in `features`.
- Keep low-level primitives in `shared/ui`, pure utilities in `shared/lib`, API/client/query-key primitives in `shared/api`.
- Prevent feature modules from importing sibling feature internals directly unless a shared entity or shared API contract is the real owner.
- Keep generated OpenAPI types and DTO mappings as the cross-layer contract, not duplicated hand-written shapes.
- Mirror backend and frontend tests by domain so future changes have obvious test homes.

## Target Structure

### Backend

```text
apps/api/app/
  api/v1/
    boards.py
    topics.py
    posts.py
    ...
  core/
    response_cache.py
    permissions.py
    ...
  models/
    forum.py
    user.py
    ...
  schemas/
    forum.py
    users.py
    ...
  repositories/
    forum/
      topic_feed.py
      topic_posts.py
      board_queries.py
      tag_queries.py
    users/
      profile_queries.py
    moderation/
      reviewable_queries.py
  services/
    forum/
      boards.py
      topics.py
      posts.py
      lifecycle.py
      notifications.py
    search.py
    admin.py
    ...
  workers/
```

### Frontend

```text
apps/web/src/
  app/
    router.ts
    layouts/
    providers/
  pages/
    board/
    topic/
    admin/
    ...
  features/
    topics/
      api.ts
      queries.ts
      model.ts
      components/
    posts/
    boards/
    moderation/
  entities/
    topic/
      model.ts
      display.ts
    board/
    user/
  shared/
    api/
    lib/
    router/
    styles/
    theme/
    ui/
```

## Technical Approach

1. Add backend `repositories/` only when extracting real duplicated or complex read/query logic.
2. Start with read-heavy forum queries because they are performance-sensitive and already have cache/cursor/visibility complexity.
3. Keep one route module per API domain for now; split only after a router has multiple independent subdomains with separate specs.
4. Introduce repository methods with explicit names such as `list_visible_topics`, `list_topic_posts`, `visible_topic_counts_by_board`, and keep visibility inputs explicit.
5. Extract backend services from `ForumService` behind stable facades so routers can migrate one domain at a time.
6. For frontend, do ownership cleanup opportunistically when touching a feature: move duplicated DTO mapping to `entities`, feature-specific queries to `features/<domain>/queries.ts`, and pure helpers to `shared/lib`.
7. Document import rules before adding lint enforcement; add lint boundaries after the codebase has obvious exceptions removed.

## Suggested Implementation Phases

### Phase 1: Guardrails

- Add a short architecture note under `.trellis/spec` or `docs/architecture`.
- Add checklist items for new backend query code and frontend feature imports.
- Define allowed dependency direction:
  - Backend: `api -> services -> repositories -> models/db`; `schemas` may be used at API boundaries, not inside repositories.
  - Frontend: `pages -> features -> entities -> shared`; `shared` must not import app/pages/features/entities.

### Phase 2: Backend Read Repositories

- Create `apps/api/app/repositories/forum/`.
- Move topic feed query construction, board topic counts, tag listing, and post-stream reads out of `ForumService`.
- Add focused tests for cursor, visibility, and sort behavior before and after extraction.

### Phase 3: Backend Service Split

- Split `ForumService` into smaller services only after repositories stabilize.
- Candidate services:
  - `BoardService`
  - `TopicService`
  - `PostService`
  - `TopicLifecycleService`
  - `TopicNotificationService`
- Keep temporary facade methods if needed so routers migrate gradually.

### Phase 4: Frontend Feature Ownership

- Audit large pages/components and identify code that is actually reusable feature logic.
- Move API calls/query hooks into their owning `features/<domain>`.
- Move display-only domain helpers into `entities/<domain>`.
- Keep page files as composition shells.

### Phase 5: Enforcement

- Add lightweight import-boundary checks after the first successful cleanup pass.
- Add PR checklist items for repository/service boundaries and frontend dependency direction.
- Add smoke or targeted regression tests for each migrated domain.

## Acceptance Criteria

- New backend read/query code has an obvious home in `repositories` or a documented reason to stay in a service.
- `ForumService` no longer needs to grow for unrelated board/topic/post behaviors.
- Frontend pages stay primarily route orchestration, not deep business logic containers.
- No route paths, response fields, colors, or visual layouts change as a side effect of structure-only work.
- Existing focused backend and frontend validation commands still pass after each migration slice.

## Out of Scope

- No one-shot rewrite of the whole backend service layer.
- No route/API version change.
- No database schema migration solely for structure cleanup.
- No frontend redesign, color/token rewrite, or component library swap.
- No broad test-suite requirement unless a migration slice touches high-risk permissions or visibility behavior.

## Immediate Next Step

Start with a small backend repository extraction for topic-list or board-topic-list reads, because it has measurable performance and complexity pressure, then follow with a frontend cleanup only when touching the related topic/board pages.
