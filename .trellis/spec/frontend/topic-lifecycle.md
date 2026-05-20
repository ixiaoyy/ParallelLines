# Frontend Topic Lifecycle Contract

## Scenario: Moderator topic management from topic detail

### 1. Scope / Trigger

- Trigger: wiring close/open, archive, pin, move, split, and merge controls to backend topic lifecycle endpoints.
- Applies to `apps/web/src/features/topics/model.ts`, `api.ts`, `queries.ts`, `components/TopicThreadToolbar.vue`, and `pages/topic/TopicDetailPage.vue`.
- This is a cross-layer contract with the backend `TopicLifecycle*` schemas and `TopicResponse.merged_into_topic_id` field.

### 2. Signatures

API wrappers in `apps/web/src/features/topics/api.ts`:

| Function | Endpoint | Payload | Return |
|---|---|---|---|
| `updateTopicLifecycle(topicId, payload)` | `PUT /topics/{topicId}/lifecycle` | `TopicLifecycleRequest` | `TopicResponse` |
| `moveTopic(topicId, payload)` | `POST /topics/{topicId}/move` | `TopicMoveRequest` | `TopicResponse` |
| `splitTopic(topicId, payload)` | `POST /topics/{topicId}/split` | `TopicSplitRequest` | `TopicLifecycleResponse` |
| `mergeTopic(topicId, payload)` | `POST /topics/{topicId}/merge` | `TopicMergeRequest` | `TopicLifecycleResponse` |

Query composables in `apps/web/src/features/topics/queries.ts`:

- `useTopicLifecycle(topicId)`
- `useMoveTopic(topicId)`
- `useSplitTopic(topicId)`
- `useMergeTopic(topicId)`

Toolbar props/emits:

```ts
canManageTopic: boolean;
topicStatus: "open" | "closed" | "archived" | "hidden";
topicPinned: boolean;
lifecyclePending: boolean;

emit("setTopicStatus", status);
emit("toggleTopicPinned");
emit("moveTopic");
emit("splitTopic");
emit("mergeTopic");
```

### 3. Contracts

- Backend DTOs stay snake_case in `TopicResponse` and request payload types (`board_slug`, `post_ids`, `target_topic_id`, `merged_into_topic_id`). Do not camelCase lifecycle payloads before sending to the API client.
- Only admins/global moderators are shown lifecycle controls in the MVP because current-user payload exposes global role; backend remains authoritative and also allows board owners/moderators.
- All lifecycle mutations use the shared API client so auth headers and API error normalization are consistent.
- Successful lifecycle/move/split/merge invalidates:
  - topic detail;
  - topic posts;
  - public/latest feeds;
  - board topic lists;
  - board directory/counters.
- Move success routes to `/b/{newBoardSlug}/t/{topicSlug}/{topicId}` using the returned `TopicResponse.board_slug`.
- Merge success routes to the target topic from `TopicLifecycleResponse.target_topic`; the source topic may return `409 topic_merged` after refresh.
- Split MVP may use prompt-based floor selection, but it must map floor numbers to currently loaded `PostResponse.id` values before calling the API.
- Reply composer is hidden and `handleReply` is guarded when `topic.status !== 'open'`; failed lifecycle or reply mutations must not clear local drafts/previews.
- Buttons are disabled while any lifecycle mutation is pending to prevent overlapping move/split/merge requests.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Viewer is not global admin/moderator | No lifecycle toolbar buttons are shown |
| Backend rejects board owner not represented in frontend role | Surface API error/alert; do not fake success |
| Topic is `closed` or `archived` | Composer hidden and submit guard refuses to post |
| Move succeeds | Navigate to route using returned board slug; invalidate old and new lists |
| Split prompt has invalid floors or includes floor 1 | Do not call API; alert the moderator |
| Merge succeeds | Navigate to target topic from response |
| Mutation pending | All lifecycle buttons disabled |

### 5. Good/Base/Bad Cases

- Good: `useMoveTopic()` calls `moveTopic()`, then invalidates topic, posts, feeds, board topics, and board counters.
- Good: split UI converts visible floor numbers to `post_ids`; the backend owns final validation.
- Base: moderator closes a topic from the toolbar and the composer immediately disappears after query invalidation/refetch.
- Bad: component calls `apiPost('/topics/...')` directly or manually mutates cached counters only on the current page.
- Bad: frontend sends `{ boardSlug }` or `{ targetTopicId }`; backend expects snake_case fields.

### 6. Tests Required

- `pnpm --dir apps/web typecheck` must verify lifecycle DTO and composable signatures.
- `pnpm --dir apps/web lint` must verify toolbar/page template correctness.
- `pnpm --dir apps/web build` must compile the route-level topic detail page.
- Browser/manual smoke before release:
  - admin closes/reopens and pins/unpins a topic;
  - admin moves a topic and lands on the new board route;
  - admin splits replies and sees both topics with stable post order;
  - admin merges a topic and lands on the target topic.

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
