# Backend Solved, Voting, Q&A, and Polls Contract

## Scenario: accepted answers, score voting, Q&A ordering, and simple polls

### 1. Scope / Trigger

- Applies when changing topic/post interaction contracts in `apps/api/app/models/forum.py`, `apps/api/app/models/interaction.py`, `apps/api/app/schemas/forum.py`, `apps/api/app/schemas/interactions.py`, `apps/api/app/services/forum.py`, `apps/api/app/services/interactions.py`, route modules, migrations, and tests.
- This is a cross-layer contract: DB counters, API payloads, frontend DTOs, and permission/error handling must stay aligned.

### 2. Signatures

Backend endpoints:

| Method | Path | Auth | Payload | Return |
|---|---:|---:|---|---|
| `PUT` | `/api/v1/topics/{topic_id}/solution` | topic author or board/global moderator | `{ "post_id": string | null }` | `TopicResponse` |
| `PUT` | `/api/v1/topics/{topic_id}/vote` | yes | `{ "value": -1 | 0 | 1 }` | `VoteStateResponse` |
| `PUT` | `/api/v1/posts/{post_id}/vote` | yes | `{ "value": -1 | 0 | 1 }` | `VoteStateResponse` |
| `GET` | `/api/v1/topics/{topic_id}/posts?sort=chronological|qa` | optional | n/a | `PostResponse[]` |
| `GET` | `/api/v1/topics/{topic_id}/poll` | optional | n/a | `PollResponse` |
| `PUT` | `/api/v1/topics/{topic_id}/poll/vote` | yes | `{ "option_ids": string[] }` | `PollResponse` |

Request/response fields:

- `TopicCreateRequest.poll: PollCreateRequest | None` where `PollCreateRequest` contains `question`, `options`, `multiple_choice`, and `closes_at`.
- `TopicResponse` includes `accepted_answer_post_id`, `solved_at`, `solved_by_id`, `answer_mode`, `vote_score`, `vote_count`, `my_vote`, and optional `poll`.
- `PostResponse` includes `accepted_answer`, `vote_score`, `vote_count`, and `my_vote`.
- `PollResponse` includes `closed`, `total_votes`, `selected_option_ids`, and ordered `options` with vote counts.

### 3. Contracts

- Only the topic author, board owner/moderator, global moderator, or admin may set/clear a solution.
- A solution must be a visible reply in the same topic; the first post cannot be accepted as the answer.
- Clearing a solution sets `accepted_answer_post_id`, `solved_at`, and `solved_by_id` to null.
- Score votes are one row per `(target_type, target_id, user_id)` in `votes`:
  - `value=1` upvotes, `value=-1` downvotes, `value=0` removes the active vote;
  - repeated identical votes are idempotent;
  - changing vote direction adjusts cached `vote_score` by the delta and keeps `vote_count` equal to active vote rows.
- Post Q&A ordering keeps the first post first, then sorts replies by accepted-answer status, `vote_score`, and `post_number`.
- Polls are created with the first topic post. Options are normalized by trimming text and preserving order.
- Poll voting permissions follow topic visibility; authenticated users who can access the topic can vote before `closes_at`.
- Closed/expired polls reject votes with `poll_closed`; single-choice polls replace the user's previous selection, while multi-choice polls replace the whole selected set.
- All new API errors use `AppError` subclasses and the standard `{ error: { code, message, details } }` response shape.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Ordinary non-author marks solution | `solution_forbidden` / 403 |
| Solution post is missing/foreign/hidden | `post_not_found` / 404 |
| First post marked as solution | `solution_must_be_reply` / 422 |
| Repeating same score vote | Same `score`/`count`; no duplicate row |
| `value=0` with no prior vote | Active value is `0`; counters unchanged |
| Poll has fewer than 2 options | Pydantic validation rejects request |
| Poll closes in the past on creation | `poll_closes_at_past` / 422 |
| Vote after `closes_at` | `poll_closed` / 422 |
| Single-choice poll receives multiple option ids | `poll_single_choice_required` / 422 |
| Poll option id is foreign/missing | `poll_option_not_found` / 404 |

### 5. Good/Base/Bad Cases

- Good: topic author accepts reply #2; topic list shows solved and post #2 has `accepted_answer=true`.
- Good: user upvotes the same post twice; `votes` row count is 1 and `Post.vote_score` remains 1.
- Base: Q&A sort returns first post first, accepted reply second, then high-score replies.
- Bad: frontend infers solved status from a tag instead of `TopicResponse.accepted_answer_post_id`.
- Bad: poll response exposes other voters for anonymous MVP polls.

### 6. Tests Required

- API tests for solution permission, clearing, and list/detail marker fields.
- API/service tests for topic and post vote idempotency and cached counters.
- API tests for Q&A post ordering.
- API tests for poll voting, single vs multi-choice replacement, and closed poll rejection.
- Regression tests: `pytest tests/test_topic_solved_voting_polls.py tests/test_interactions_notifications.py tests/test_topic_lifecycle.py -q` plus full backend suite before finishing.
- Migration verification on a clean MySQL database URL before release.
