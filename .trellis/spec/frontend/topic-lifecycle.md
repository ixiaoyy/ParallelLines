# Frontend Topic Lifecycle Contract

## Scenario: Moderator topic management from topic detail

### 1. Scope / Trigger

- Trigger: wiring close/open, pin, and move controls to backend topic lifecycle endpoints.
- Applies to `apps/web/src/features/topics/model.ts`, `api.ts`, `queries.ts`, `components/TopicThreadToolbar.vue`, and `pages/topic/TopicDetailPage.vue`.
- This is a cross-layer contract with the backend `TopicLifecycle*` schemas.

### 2. Signatures

API wrappers in `apps/web/src/features/topics/api.ts`:

| Function | Endpoint | Payload | Return |
|---|---|---|---|
| `updateTopicLifecycle(topicId, payload)` | `PUT /topics/{topicId}/lifecycle` | `TopicLifecycleRequest` | `TopicResponse` |
| `moveTopic(topicId, payload)` | `POST /topics/{topicId}/move` | `TopicMoveRequest` | `TopicResponse` |

Query composables in `apps/web/src/features/topics/queries.ts`:

- `useTopicLifecycle(topicId)`
- `useMoveTopic(topicId)`

Toolbar props/emits:

```ts
canManageTopic: boolean;
topicStatus: "open" | "closed" | "archived" | "hidden";
topicPinned: boolean;
lifecyclePending: boolean;

emit("setTopicStatus", status);
emit("toggleTopicPinned");
emit("moveTopic");
```

### 3. Contracts

- Backend DTOs stay snake_case in `TopicResponse` and request payload types (`board_slug`, `merged_into_topic_id`). Do not camelCase lifecycle payloads before sending to the API client.
- Only admins/global moderators are shown lifecycle controls in the MVP because current-user payload exposes global role; backend remains authoritative and also allows board owners/moderators.
- All lifecycle mutations use the shared API client so auth headers and API error normalization are consistent.
- Successful lifecycle/move invalidates:
  - topic detail;
  - topic posts;
  - public/latest feeds;
  - board topic lists;
  - board directory/counters.
- Move success routes to `/b/{newBoardSlug}/t/{topicSlug}/{topicId}` using the returned `TopicResponse.board_slug`.
- Archived backend records are shown to users as “关闭” / “已关闭”; avoid exposing the backend term “归档” in topic detail actions or reply-blocking copy.
- Split/merge are intentionally not exposed in the topic toolbar because they are rare moderator power tools and make the common action menu harder to understand. Do not reintroduce frontend split/merge actions without an explicit product request.
- Reply composer is hidden and `handleReply` is guarded when `topic.status !== 'open'`; failed lifecycle or reply mutations must not clear local drafts/previews.
- Buttons are disabled while any lifecycle mutation is pending to prevent overlapping status/move requests.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Viewer is not global admin/moderator | No lifecycle toolbar buttons are shown |
| Backend rejects board owner not represented in frontend role | Surface API error/alert; do not fake success |
| Topic is `closed` or `archived` | Composer hidden and submit guard refuses to post |
| Move succeeds | Navigate to route using returned board slug; invalidate old and new lists |
| Mutation pending | All lifecycle buttons disabled |

### 5. Good/Base/Bad Cases

- Good: `useMoveTopic()` calls `moveTopic()`, then invalidates topic, posts, feeds, board topics, and board counters.
- Good: archived topics use user-facing copy like “关闭” / “已关闭” instead of “归档”.
- Base: moderator closes a topic from the toolbar and the composer immediately disappears after query invalidation/refetch.
- Bad: component calls `apiPost('/topics/...')` directly or manually mutates cached counters only on the current page.
- Bad: frontend sends `{ boardSlug }` or `{ targetTopicId }`; backend expects snake_case fields.
- Bad: adding prompt-based “拆分” / “合并” actions back to the topic toolbar without a new product decision.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` must verify lifecycle DTO and composable signatures.
- `pnpm --dir apps/web lint` must verify toolbar/page template correctness.
- `pnpm --dir apps/web build` must compile the route-level topic detail page.
- Browser/manual smoke before release:
  - admin closes/reopens and pins/unpins a topic;
  - admin moves a topic and lands on the new board route;
  - admin closes a discussion and the reply composer is hidden with “已关闭” copy.

### 7. Wrong vs Correct

#### Wrong

```ts
await apiPost(`/topics/${topicId}/move`, { boardSlug });
queryClient.invalidateQueries();
```

#### Correct

```ts
const moved = await moveTopic(topicId, { board_slug: boardSlug, note });
invalidateTopicLifecycleQueries(queryClient, moved.id, moved.board_slug);
router.replace(`/b/${moved.board_slug}/t/${moved.slug}/${moved.id}`);
```
