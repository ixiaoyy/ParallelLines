# Frontend Forum API Wiring Contract

## Scenario: Fixture-to-real board/topic/post data transition

### 1. Scope / Trigger

- Trigger: wiring board directory, board detail, topic detail, new-topic, and reply composer from static fixtures to FastAPI `/api/v1` endpoints.
- Applies to `apps/web/src/features/boards/`, `apps/web/src/features/topics/`, `apps/web/src/features/posts/`, `shared/api/client.ts`, and route pages under `pages/board` and `pages/topic`.

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
| `createTopic(boardSlug, payload)` | `POST /api/v1/boards/{slug}/topics` | `TopicResponse` |
| `createPost(topicId, payload)` | `POST /api/v1/topics/{topic_id}/posts` | `PostResponse` |

Query composables:

- `useBoards()`
- `useBoardDetail(slug)`
- `useTopicFeed(sort)`
- `useBoardTopics(boardSlug, sort)`
- `useTopicDetail(topicId)`
- `useTopicPosts(topicId)`
- `useTopicSearch(params)`
- `useCreateTopic()`
- `useCreatePost(topicId)`

### 3. Contracts

- Backend DTOs stay snake_case; UI VMs stay camelCase.
- Mapping functions are the only boundary where DTO fields are transformed:
  - `toBoardSummary(BoardResponse): BoardSummary`
  - `toTopicCard(TopicResponse): TopicCardVM`
  - `toPostItem(PostResponse): PostItemVM`
- Public read queries should fall back to `shared/api/mockForum.ts` on network/API failure so the frontend prototype remains usable without a running backend.
- Empty backend seed data may also fall back to fixtures for discovery surfaces until seed data exists.
- Authenticated write mutations (`createTopic`, `createPost`) must use `shared/api/client.ts` so `Authorization` is attached consistently.
- If writes fail because the user is not logged in or the backend is down, keep the current draft/preview state rather than dropping user content.
- Search route state belongs in URL query parameters (`q`, `sort`, `board`, `tag`, `author`) so result pages are shareable.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Backend unavailable | Read queries return fixture data; UI still renders |
| Backend returns empty public lists during early setup | Discovery surfaces use fixtures instead of blank homepage |
| Missing access token on create topic/reply | Mutation fails; page keeps draft and displays preview/helper copy |
| Topic/board not found | Page shows existing empty-state component |
| Backend DTO dates are ISO strings | UI formatting happens via `relativeTime` only after mapping |
| Search query empty | Search page shows guidance instead of firing an empty API request |

### 5. Good/Base/Bad Cases

- Good: board page reads `TopicResponse[]`, maps to `TopicCardVM[]`, then applies URL query filters locally.
- Base: logged-in user creates a topic; frontend posts `{ title, raw_md, tags }`, then routes to `/t/{slug}/{id}`.
- Bad: page components import `apiGet` directly and manually read `topic.reply_count` in templates.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` verifies DTO/VM and query composable types.
- `pnpm --dir apps/web lint` verifies no direct fetches outside API modules and no template issues.
- `pnpm --dir apps/web build` verifies route-level dynamic imports compile.
- Backend tests for board/topic/post endpoints must keep passing when frontend contracts depend on fields.

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
