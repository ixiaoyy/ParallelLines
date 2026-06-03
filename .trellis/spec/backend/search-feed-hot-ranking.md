# Backend Search, Feed, and Hot Ranking Contract

## Scenario: Public topic discovery through feeds, search filters, and hot score recompute

### 1. Scope / Trigger

- Trigger: changing latest/top/hot feeds, board-scoped topic lists, full-text search
  filters, search index synchronization, search logs, tag cloud data, cursor
  pagination, or hot score recomputation.
- Applies to `ForumService.list_topics`, `ForumService.list_tags`,
  `SearchService`, `SearchIndexService`, `app/models/search.py`,
  `app/api/v1/topics.py`, `app/api/v1/boards.py`, `app/api/v1/search.py`,
  `app/api/v1/tags.py`, Alembic search migrations, and
  `app/workers/background_jobs.py`.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/api/v1/topics?sort=&q=&board=&tag=&author=&cursor=&limit=` | no | Public topic feed and filtered topic list |
| `GET` | `/api/v1/boards/{slug}/topics?sort=&q=&tag=&author=&cursor=&limit=` | no | Board-scoped feed/search |
| `GET` | `/api/v1/search?q=&board=&tag=&author=&status=&created_after=&created_before=&sort=&cursor=&limit=` | no | Search visible indexed topics by title, visible post Markdown, tag, and author |
| `GET` | `/api/v1/tags?limit=` | no | Public tag cloud ordered by actual topic usage |

Service/worker:

- `ForumService.list_topics(board_slug=None, sort="latest", limit=30, query=None, tag=None, author=None, cursor=None) -> list[Topic]`
- `ForumService.list_tags(limit=30) -> list[Tag]`
- `SearchService.search_topics(query, filters, sort="relevance", cursor=None, limit=30, current_user=None) -> list[Topic]`
- `SearchIndexService.sync_topic(topic_id) -> SearchDocument | None`
- `SearchIndexService.remove_topic(topic_id) -> None`
- `SearchIndexService.rebuild_all() -> {"synced_count": int, "removed_count": int}`
- `recompute_hot_scores(session: AsyncSession) -> int`
- Worker handler: `rebuild_search_index` on the unified background worker.

DB tables:

| Table | Fields | Contract |
|---|---|---|
| `search_documents` | `topic_id`, `board_id`, `author_id`, `author_username`, `topic_status`, `title`, `body`, `tags_text`, `indexed_at` | One materialized searchable document per non-hidden topic. `body` contains only visible post Markdown. |
| `search_logs` | `user_id`, `query`, `normalized_query`, `filters`, `result_count`, `has_results`, `created_at` | Append-only query log for no-result analysis and hot terms. |
| `topic_views` | `topic_id`, `viewer_key`, `first_viewed_at` | One row per counted topic viewer. `viewer_key` is a prefixed hash for either the authenticated user id or the anonymous visitor id. |

### 3. Contracts

- All routes return `ApiResponse[list[TopicResponse]]`.
- Cursor is an opaque string based on `Topic.last_posted_at` plus `Topic.id`; latest topic-list cursors also include the current `Topic.pinned` rank so pinned-first pagination does not skip or duplicate rows. Response meta includes `next_cursor` when `len(topics) == limit`.
- Search query matches `search_documents.title`, visible aggregated `body`,
  `tags_text`, or `author_username`; `LIKE` wildcards must be escaped before
  DB matching.
- `/search` default sort is `relevance`, ordered by weighted title/tag/body
  match, then `Topic.last_posted_at desc`, then `Topic.id desc` for stability.
- `tag` is normalized with `normalize_tag_name` and matched against tag `slug` or `name`.
- `author` matches `User.username`.
- `sort` values:
  - `relevance`: weighted search rank, then latest activity
  - `latest`: `pinned desc`, then `last_posted_at desc`, then `id desc`
  - `hot`: `hot_score desc`, then `last_posted_at desc`
  - `top`: `like_count desc`, then `reply_count desc`
- `/tags` returns `ApiResponse[list[TagResponse]]` and must include only tags with `topic_count > 0`, ordered by `topic_count desc`, then `name`.
- Hot feed/tag list routes may use a short-lived response cache for perceived
  speed. Cache keys must include the full filter/sort/cursor/limit set and a
  visibility scope (`anonymous` or the authenticated user id) so private-board
  visibility and per-user reaction state never leak across users. `/search`
  must not skip execution through a response cache because each search request
  writes a `search_logs` row.
- Hot score recompute is idempotent and uses `calculate_hot_score(reply_count, like_count, view_count)`.
- `SearchIndexService.sync_topic` must run in the same transaction for topic
  create, reply, first-post edit, revision restore, reply delete, topic status
  changes, move, split, merge, and moderation hide/restore paths.
- Hidden topics remove their `search_documents` row. Hidden posts are excluded
  from `body`; they must not make a topic discoverable.
- Every `/search` request writes a `search_logs` row with normalized query,
  safe filter snapshot, result count, and anonymous/authenticated user id.
- `GET /api/v1/topics/{topic_id}` is the only public topic-read route that
  records a view. Internal service reads and `GET /topics/{topic_id}/posts`
  must call the plain topic lookup and must not increment `view_count`.
- View counting is deduplicated through `topic_views(topic_id, viewer_key)`.
  Authenticated users dedupe by account id hash. Anonymous visitors dedupe by
  `X-ParallelLines-Visitor`; if that stable header is absent or invalid, do not
  increment rather than counting every request as a different person.
- When a first-time view is recorded, update both `topics.view_count` and
  `topics.hot_score = calculate_hot_score(reply_count, like_count, view_count)`
  in the same transaction.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Unknown board on board-scoped list/search | `NotFoundError("board_not_found")` |
| Empty or missing `q` on `/search` | FastAPI validation error in project error envelope |
| Wildcards in search query (`%`, `_`, `\`) | Escaped before `ilike`; never treated as raw pattern control |
| Cursor beyond available data | Empty `data`, `next_cursor: null` |
| Deleted topic | Excluded from feeds/search/hot recompute |
| Hidden post body matches query | Topic is not returned unless another visible field matches |
| Private board topic matches query | Anonymous/stranger does not see it; member/owner does |
| Post is edited or revision restored | Search document reflects new visible body before commit |
| Topic is hidden/merged/deleted | Search document is removed in the same transaction |
| `/search` has zero results | `search_logs.has_results=false`, `result_count=0` |
| Tag with no topics | Excluded from `/tags` |
| Invalid tag limit (`0` or `>100`) | FastAPI validation error in project error envelope |
| Invalid search `status` | FastAPI validation error in project error envelope |
| Same authenticated user opens a topic twice | One `topic_views` row; `view_count` increases once |
| Same anonymous visitor header opens a topic twice | One `topic_views` row; `view_count` increases once |
| Anonymous request has no stable visitor header | Topic is returned, but `view_count` does not increment |

### 5. Good/Base/Bad Cases

- Good: `GET /search?q=callback` finds a topic whose first post contains `callback` even when title does not.
- Good: `GET /search?q=callback` ranks a title match above a body-only match,
  then uses latest activity and id as stable tie-breakers.
- Good: `GET /boards/{slug}/topics?sort=latest` lists pinned topics before regular topics, and the next cursor continues after the pinned row without duplicating it.
- Good: `GET /tags?limit=5` returns real `TagResponse` rows sorted by `topic_count`, for home tag cloud.
- Good: topic detail increments views once per authenticated user or stable
  anonymous visitor id, and repeated opens return the same `view_count`.
- Good: `ForumService.update_post` updates `posts.raw_md` and then calls
  `SearchIndexService(session).sync_topic(post.topic_id)` before commit.
- Base: `GET /topics?tag=csv&sort=latest` returns only topics with normalized CSV tag.
- Bad: router builds SQL directly or interpolates query text into SQL strings.
- Bad: moderation hides a post but leaves the old `search_documents.body`
  containing hidden text.

### 6. Tests Required

- API test for search by post body.
- API test for relevance order, special-character escaping, status/date/board/tag/author filters, and search logging.
- API test for tag filter and cursor meta.
- API test for `GET /tags` returning persisted tag names and `topic_count`.
- API test for `GET /topics/{id}` counting one view per authenticated user and
  per stable anonymous visitor, while `/topics/{id}/posts` and unidentified
  anonymous requests do not increment.
- Feed ordering test for latest/hot/top when counters differ, including latest pinned-first ordering and cursor continuation.
- Index sync tests for create, reply, first-post edit, revision restore,
  hide/restore post, hide/restore topic, move/split/merge.
- Privacy tests proving indexed private-board content remains filtered by board
  membership.
- Worker test proving `recompute_hot_scores` updates all non-deleted topics and is safe to rerun through the unified background worker module.
- Worker test proving `rebuild_search_index` backfills non-hidden topics and removes stale documents.

### 7. Wrong vs Correct

#### Wrong

```python
statement = text(f"select * from topics where title like '%{q}%'")
```

#### Correct

```python
pattern = f"%{escape_like(query.strip())}%"
statement = statement.where(or_(Topic.title.ilike(pattern, escape="\\"), post_match))
```

#### Wrong

```python
post.raw_md = payload.raw_md
await session.commit()  # search_documents still contains the previous body
```

#### Correct

```python
post.raw_md = payload.raw_md
await SearchIndexService(session).sync_topic(post.topic_id)
await session.commit()
```
