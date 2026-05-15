# Backend Search, Feed, and Hot Ranking Contract

## Scenario: Public topic discovery through feeds, search filters, and hot score recompute

### 1. Scope / Trigger

- Trigger: changing latest/top/hot feeds, board-scoped topic lists, search filters, cursor pagination, or hot score recomputation.
- Applies to `ForumService.list_topics`, `app/api/v1/topics.py`, `app/api/v1/boards.py`, `app/api/v1/search.py`, and `app/workers/hot_ranking.py`.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `GET` | `/api/v1/topics?sort=&q=&board=&tag=&author=&cursor=&limit=` | no | Public topic feed and filtered topic list |
| `GET` | `/api/v1/boards/{slug}/topics?sort=&q=&tag=&author=&cursor=&limit=` | no | Board-scoped feed/search |
| `GET` | `/api/v1/search?q=&board=&tag=&author=&sort=&cursor=&limit=` | no | Search public topics by title and post raw Markdown |

Service/worker:

- `ForumService.list_topics(board_slug=None, sort="latest", limit=30, query=None, tag=None, author=None, cursor=None) -> list[Topic]`
- `recompute_hot_scores(session: AsyncSession) -> int`

### 3. Contracts

- All routes return `ApiResponse[list[TopicResponse]]`.
- Cursor is an ISO datetime string based on `Topic.last_posted_at`; response meta includes `next_cursor` when `len(topics) == limit`.
- Search query matches `Topic.title` or any matching `Post.raw_md`; `LIKE` wildcards must be escaped via `escape_like`.
- `tag` is normalized with `normalize_tag_name` and matched against tag `slug` or `name`.
- `author` matches `User.username`.
- `sort` values:
  - `latest`: `last_posted_at desc`
  - `hot`: `hot_score desc`, then `last_posted_at desc`
  - `top`: `like_count desc`, then `reply_count desc`
- Hot score recompute is idempotent and uses `calculate_hot_score(reply_count, like_count, view_count)`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Unknown board on board-scoped list/search | `NotFoundError("board_not_found")` |
| Empty or missing `q` on `/search` | FastAPI validation error in project error envelope |
| Wildcards in search query (`%`, `_`, `\`) | Escaped before `ilike`; never treated as raw pattern control |
| Cursor beyond available data | Empty `data`, `next_cursor: null` |
| Deleted topic | Excluded from feeds/search/hot recompute |

### 5. Good/Base/Bad Cases

- Good: `GET /search?q=callback` finds a topic whose first post contains `callback` even when title does not.
- Base: `GET /topics?tag=csv&sort=latest` returns only topics with normalized CSV tag.
- Bad: router builds SQL directly or interpolates query text into SQL strings.

### 6. Tests Required

- API test for search by post body.
- API test for tag filter and cursor meta.
- Feed ordering test for latest/hot/top when counters differ.
- Worker test proving `recompute_hot_scores` updates all non-deleted topics and is safe to rerun.

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
