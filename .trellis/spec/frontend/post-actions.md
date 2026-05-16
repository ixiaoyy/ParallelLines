# Frontend Post Actions Contract

## Scope

Applies to `TopicDetailPage`, `PostItem`, and post feature API/query modules. Post action buttons must be real controls with visible feedback; no inert buttons are allowed in topic/post action bars.

## Contracts

- `PostItemVM` includes `id`, `topicId`, `userId`, `floor`, `authorName`, `rawMd`, `cookedHtml`, counts, and timestamps so actions do not inspect backend DTOs in components.
- `PATCH /posts/{id}` is wrapped by `updatePost(postId, { raw_md })` and exposed as `useUpdatePost(topicId)`; successful edits invalidate topic posts and topic detail queries.
- Topic toolbar copy-link writes the current topic URL without hash. If clipboard access is blocked, update `location.hash` and show a role=`status` fallback message.
- Only-author filtering is page-local state and filters displayed floors to the topic author's posts; it must not mutate server state.
- Code copy copies the first `<pre><code>` text from sanitized `cookedHtml` and shows visible status.
- Quote emits the full `PostItemVM`; topic detail inserts `> author #floor` plus a raw Markdown/plain-text excerpt into the reply composer.
- Edit controls are shown only when a verified logged-in current user id from `useCurrentUser().data.id` matches `post.userId`; do not decode a local token as an ownership fallback after `/auth/me` fails.
- Reply composers preserve drafts until `useCreatePost` succeeds. Unauthenticated replies must keep the draft, show a visible status, and guide the user to `/auth?redirect=<current path>`.

## Validation

- Run `pnpm --dir apps/web typecheck` after changing VM/API/query types.
- Run `pnpm --dir apps/web lint` after changing Vue templates or smoke specs.
- Smoke tests should click copy link, only-author, quote, code copy, edit, notification, search, and boards navigation with role/name selectors where possible.

