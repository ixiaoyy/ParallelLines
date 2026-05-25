# Frontend Solved, Voting, Q&A, and Polls Contract

## Scenario: accepted answer UI, score voting, Q&A order, and poll voting

### 1. Scope / Trigger

- Applies when changing topic/post DTOs, API wrappers, query composables, topic detail, post actions, composer poll fields, and board/list solved badges.
- Backend DTOs stay snake_case; frontend VMs stay camelCase at mapping boundaries.

### 2. Signatures

Frontend API wrappers:

| Function | Endpoint | Payload | Return |
|---|---|---|---|
| `setTopicSolution(topicId, payload)` | `PUT /topics/{topicId}/solution` | `TopicSolutionRequest` | `TopicResponse` |
| `setTopicVote(topicId, payload)` | `PUT /topics/{topicId}/vote` | `VoteRequest` | `VoteStateResponse` |
| `setPostVote(postId, payload)` | `PUT /posts/{postId}/vote` | `VoteRequest` | `VoteStateResponse` |
| `fetchPosts(topicId, sort)` | `GET /topics/{topicId}/posts?sort=` | n/a | `PostResponse[]` |
| `votePoll(topicId, payload)` | `PUT /topics/{topicId}/poll/vote` | `PollVoteRequest` | `PollResponse` |

VM additions:

- `TopicCardVM`: `authorId`, `acceptedAnswerPostId`, `solvedAt`, `voteScore`, `voteCount`, `myVote`, optional `poll`.
- `PostItemVM`: `acceptedAnswer`, `voteScore`, `voteCount`, `myVote`.
- `PollVM`: `id`, `question`, `multipleChoice`, `closed`, `totalVotes`, `selectedOptionIds`, ordered options.

### 3. Contracts

- Solved badges must use `acceptedAnswerPostId`, not tag text heuristics.
- Topic author and global admin/moderator can see solution controls in the MVP; backend remains authoritative for board-scoped moderators.
- Solution mutations invalidate topic detail, post stream, feeds, and board topic lists.
- Post score vote controls are idempotent and keep the displayed score from the mutation response; unauthenticated users are routed to auth or shown a draft-preserving message.
- Q&A order is an explicit topic-detail toggle that changes the post query key to `chronological` or `qa`.
- Poll cards preserve the selected options locally until the mutation succeeds or the backend returns validation errors; closed polls disable controls and show final counts.
- Topic composer may attach one simple poll to a new topic; it must send snake_case `multiple_choice` and `closes_at` fields.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Solution mutation forbidden | Visible toolbar/post status, no fake solved marker |
| Accepted answer present | Topic hero/list badge and accepted post styling visible |
| Q&A sort active | First post remains first; accepted/high-score replies appear earlier |
| Anonymous vote/poll attempt | Shows login guidance; current draft/selection is preserved |
| Poll expired | Options disabled and backend `poll_closed` copy shown if user tries to submit |
| Build/type errors | Block finish until `pnpm --dir apps/web typecheck`, `lint`, and `build` pass |

### 5. Tests / Verification

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- Browser smoke: topic detail shows solved badge, Q&A toggle, vote controls, and poll card without console errors.
