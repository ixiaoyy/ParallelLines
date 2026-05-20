# Backend User Content Operations Contract

## Scope

Applies to public user profile reads, authored topic lists, and post editing under `/api/v1`.

## API Signatures

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/users/{username}` | public | Return public user profile without email. |
| `GET /api/v1/users/{username}/topics?limit=` | public | Return visible topics authored by username using `TopicResponse`. |
| `PATCH /api/v1/posts/{post_id}` | active user | Update post Markdown/rendered HTML and optionally save `edit_reason` into revision history. |

## Response Contracts

`GET /users/{username}` returns:

- `id`, `username`, `avatar_url`, `role`, `status`, `created_at`
- `topic_count`: count of non-hidden topics authored by the user
- `post_count`: count of non-hidden posts authored by the user where the parent topic is not hidden
- Never include `email`.

`GET /users/{username}/topics` returns `TopicResponse[]` ordered by latest activity and excludes topics where `deleted_at is not null`.

`PATCH /posts/{post_id}` accepts `{ "raw_md": string, "edit_reason"?: string | null }` and returns `PostResponse` after updating `raw_md`, `cooked_html`, and `updated_at`. It must create a `post_revisions` row before overwriting live content; see `post-revisions-history.md`.

## Permissions and Errors

| Case | Error/Behavior |
|---|---|
| Unknown user | `user_not_found` / 404 |
| Unknown, hidden, or hidden-topic post edit target | `post_not_found` / 404 |
| Empty Markdown after trimming | `empty_post` / 422 |
| Author edits own non-hidden post | 200 |
| Global `admin`/`moderator` edits a non-hidden post | 200 |
| Board `owner`/`moderator` edits a non-hidden post in their board | 200 |
| Ordinary user edits another user's post | `permission_denied` / 403 |

## Implementation Notes

- Routers stay thin and delegate queries/transactions to `ForumService`.
- Reuse the forum Markdown renderer so create/reply/edit paths produce consistent sanitized HTML.
- Public lists/counts must apply the same hidden-topic filter used by topic feeds.

## Tests Required

- Public user profile does not leak email.
- Authored topic list filters hidden topics.
- Author can edit own post.
- Ordinary user cannot edit another user's post.
- Board owner/moderator can edit posts in their board.
