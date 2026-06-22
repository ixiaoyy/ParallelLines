# Frontend Forum API Wiring Contract

## Scenario: Real API board/topic/post/tag data wiring

### 1. Scope / Trigger

- Trigger: wiring board directory, board detail, topic detail, new-topic, search, home discovery, tag cloud, and reply composer to FastAPI `/api/v1` endpoints.
- Applies to `apps/web/src/features/boards/`, `apps/web/src/features/topics/`, `apps/web/src/features/posts/`, `apps/web/src/features/tags/`, `shared/api/client.ts`, and route pages under `pages/home`, `pages/board`, `pages/search`, and `pages/topic`.

### 2. Signatures

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `fetchBoards()` | `GET /api/v1/boards` | `BoardResponse[]` |
| `fetchBoardDetail(slug)` | `GET /api/v1/boards/{slug}` | `BoardDetailResponse` |
| `fetchTopics(sort, limit)` | `GET /api/v1/topics?sort=&limit=` | `TopicResponse[]` |
| `fetchBoardTopics(boardSlug, sort, limit)` | `GET /api/v1/boards/{slug}/topics?sort=&limit=` | `TopicResponse[]` |
| `fetchTopic(topicId)` | `GET /api/v1/topics/{topic_id}` | `TopicResponse` |
| `fetchPosts(topicId)` | `GET /api/v1/topics/{topic_id}/posts` | `PostResponse[]` |
| `searchTopics(params)` | `GET /api/v1/search?q=&board=&tag=&author=&sort=&limit=` | `TopicResponse[]` |
| `fetchTags(limit)` | `GET /api/v1/tags?limit=` | `TagResponse[]` |
| `createTopic(boardSlug, payload)` | `POST /api/v1/boards/{slug}/topics` | `TopicResponse` |
| `createPost(topicId, payload)` | `POST /api/v1/topics/{topic_id}/posts` | `PostResponse` |
| `updateTopicLifecycle(topicId, payload)` | `PUT /api/v1/topics/{topic_id}/lifecycle` | `TopicResponse` |
| `moveTopic(topicId, payload)` | `POST /api/v1/topics/{topic_id}/move` | `TopicResponse` |

Query composables:

- `useBoards()`
- `useBoardDetail(slug)`
- `useTopicFeed(sort)`
- `useBoardTopics(boardSlug, sort)`
- `useTopicDetail(topicId)`
- `useTopicPosts(topicId)`
- `useTopicSearch(params)`
- `useTags(limit)`
- `useCreateTopic()`
- `useCreatePost(topicId)`
- `useTopicLifecycle(topicId)`
- `useMoveTopic(topicId)`

### 3. Contracts

- Backend DTOs stay snake_case; UI VMs stay camelCase.
- Mapping functions are the only boundary where DTO fields are transformed:
  - `toBoardSummary(BoardResponse): BoardSummary`
  - `toTopicCard(TopicResponse): TopicCardVM`
  - `toPostItem(PostResponse): PostItemVM`
  - `toTagItem(TagResponse): TagItemVM`
- Social response fields must be mapped at the DTO/VM boundary:
  - `TopicResponse.liked_by_me/bookmarked_by_me/bookmark_count/share_url` →
    `TopicCardVM.likedByMe/bookmarkedByMe/bookmarkCount/shareUrl`
  - `TopicResponse.author_level` → `TopicCardVM.authorLevel`
  - `PostResponse.liked_by_me/share_url` → `PostItemVM.likedByMe/shareUrl`
  - `PostResponse.author_level` → `PostItemVM.authorLevel`
- Production read queries must not silently fall back to static fixtures or mock forum data. Network/API failures surface through TanStack Query error state and page-level empty/error UI.
- Empty API responses render honest empty states and calls to action; discovery surfaces must not invent boards, topics, posts, or tags.
- Authenticated write mutations (`createTopic`, `createPost`) must use `shared/api/client.ts` so `Authorization` is attached consistently.
- If writes fail because the user is not logged in or the backend is down, keep the current draft/preview state rather than dropping user content.
- Topic lifecycle payloads stay snake_case (`board_slug`) and are owned by `features/topics/api.ts`; pages/components must call the lifecycle composables instead of direct `apiPost`/`apiPut`.
- Lifecycle mutations invalidate topic detail, topic posts, public/latest feeds, board topic lists, and board counters; move navigation must use the returned `TopicResponse`.
- Frontend topic-detail action menus expose close/open, pin, move, report, and delete. Archived backend records are also shown as “已关闭”. Split/merge remain intentionally hidden from frontend menus unless product explicitly asks for those moderator power tools.
- Search route state belongs in URL query parameters (`q`, `sort`, `board`, `tag`, `author`) so result pages are shareable.
- Static fixture/sample data is allowed only in explicitly named design-system, story, or test modules. Production page/query paths must not import `shared/api/mockForum.ts` or notification mocks.
- `shared/api/client.ts` attaches `X-ParallelLines-Visitor` from a stable
  `parallellines.visitor_id` localStorage value so anonymous topic detail views
  can be deduplicated by the backend. If localStorage is unavailable, omit the
  header instead of generating a per-request id that would inflate view counts.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Backend unavailable | Query enters error state; page shows a visible API unavailable/error message and no fake content |
| Backend returns empty public lists during early setup | Discovery surfaces show empty states and publish/explore calls to action |
| Missing access token on create topic/reply | Mutation fails; page keeps draft and displays preview/helper copy |
| Closed or archived topic | Reply composer is hidden/guarded and lifecycle controls remain moderator-only |
| Move succeeds | Related topic/board/feed queries invalidate and navigation uses returned topic fields |
| Topic/board not found | Page shows existing empty-state component |
| Backend DTO dates are ISO strings | UI formatting happens via `relativeTime` only after mapping |
| Search query empty | Search page shows guidance instead of firing an empty API request |
| Tag API unavailable | Home tag cloud shows a tag API error/empty state and does not render static tags |
| Same browser opens topic detail twice while anonymous | Same `X-ParallelLines-Visitor`; backend view count increases only once |
| Browser storage unavailable | API requests omit visitor header; backend returns topic but does not count anonymous view |

### 5. Good/Base/Bad Cases

- Good: board page reads `TopicResponse[]`, maps to `TopicCardVM[]`, and renders an explicit error card if the query fails.
- Base: logged-in user creates a topic; frontend posts `{ title, raw_md, tags }`, then routes to `/t/{slug}/{id}`.
- Bad: page components catch API errors and return `mockTopics`, or import `apiGet` directly and manually read `topic.reply_count` in templates.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` verifies DTO/VM and query composable types.
- `pnpm --dir apps/web lint` verifies no direct fetches outside API modules and no template issues.
- `pnpm --dir apps/web build` verifies route-level dynamic imports compile.
- `pnpm --dir apps/web test:smoke` must verify the lightweight UI-created auth/topic/reply path against the real API; broader board/tag discovery regressions belong in focused or extended Playwright suites.
- Backend tests for board/topic/post endpoints must keep passing when frontend contracts depend on fields.
- Backend tests for `GET /api/v1/tags` must verify tag responses are real DB rows ordered by usage.
- Backend `test_topic_lifecycle.py` and frontend `typecheck` must stay in sync for `TopicLifecycle*` payload/response fields.

### 7. Wrong vs Correct

#### Wrong

```ts
const topics = await apiGet<TopicResponse[]>("/topics");
const title = topics[0].reply_count;
```

#### Correct

```ts
const topics = await fetchTopics("latest");
return topics.map(toTopicCard);
```
