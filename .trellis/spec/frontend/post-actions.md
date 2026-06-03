# Frontend Post Actions Contract

## Scope

Applies to `TopicDetailPage`, `PostItem`, and post feature API/query modules. Post action buttons must be real controls with visible feedback; no inert buttons are allowed in topic/post action bars.

## Contracts

- `PostItemVM` includes `id`, `topicId`, `userId`, `floor`, `authorName`, `rawMd`,
  `cookedHtml`, counts, timestamps, `likedByMe`, and `shareUrl` so actions do not inspect backend
  DTOs in components.
- `PATCH /posts/{id}` is wrapped by `updatePost(postId, { raw_md })` and exposed as `useUpdatePost(topicId)`; successful edits invalidate topic posts and topic detail queries.
- `PATCH /posts/{id}` may include `{ edit_reason }`; the edit form should preserve the draft and optional reason until the mutation succeeds.
- `GET /posts/{id}/revisions` is wrapped by `usePostRevisions(postId, enabled)` and mapped from snake_case DTOs to camelCase revision VMs before rendering.
- `POST /posts/{id}/revisions/{revisionId}/restore` is wrapped by `useRestorePostRevision(topicId)`; successful restore invalidates the topic detail, post stream, and revision list.
- Topic toolbar copy-link writes the backend-provided `TopicCardVM.shareUrl` as an absolute URL
  without hash. If clipboard access is blocked, update `location.hash` and show a role=`status`
  fallback message.
- Post copy-link writes `PostItemVM.shareUrl` as an absolute URL including `#post-{floor}`; if the
  clipboard is blocked, update the address hash and show a visible status.
- Only-author filtering is page-local state and filters displayed floors to the topic author's posts; it must not mutate server state.
- Topics tagged `漫画阅读` enable comic-reader mode for the first/original post only; replies remain normal posts so comment images are not pulled into the reader.
- Comic-reader mode extracts image pages from sanitized `cookedHtml` and keeps only the active page image mounted. The reader chrome must stay minimal: show page count plus previous/next controls only; do not render intro/explanatory post text, a range/progress slider, captions, or instructional copy such as preload/keyboard hints.
- Comic-reader mode may preload only the immediate next page as a delayed low-priority background image request; it must not eagerly mount or request every page at once.
- Desktop comic-reader layouts may use a right-side page rail to reduce empty space. For upload-backed
  pages, the rail must use the dedicated `/uploads/{id}/thumbnail` API and may warm those thumbnails
  in the background; full-size page images remain limited to the active page plus delayed next-page
  preload. For non-upload images without a thumbnail API, render real rail images only for the
  active/neighbor pages and placeholders for distant pages.
- On small screens, comic-reader images must prioritize full viewport width and vertical scrolling; do not cap page height in a way that shrinks a tall manga page into a small centered thumbnail.
- Read-only topic detail rendering must not statically import `md-editor-v3`; edit/reply editors should load asynchronously after browser idle time so first image rendering is not blocked by the editor bundle.
- Code copy copies the first `<pre><code>` text from sanitized `cookedHtml` and shows visible status.
- Quote emits the full `PostItemVM`; topic detail inserts `> author #floor` plus a raw Markdown/plain-text excerpt into the reply composer.
- Edit controls are shown only when a verified logged-in current user id from `useCurrentUser().data.id` matches `post.userId`; do not decode a local token as an ownership fallback after `/auth/me` fails.
- Revision history controls may be shown to the author and global moderators/admins from `/auth/me`; board-scoped moderator permissions are still enforced by the backend if the UI cannot infer them.
- Reply composers preserve drafts until `useCreatePost` succeeds. Unauthenticated replies must keep the draft, show a visible status, and guide the user to `/auth?redirect=<current path>`.
- Topic/detail social action bars may expose an invite entry, but it should route to the existing
  `/invites` center (`my-invites` route) rather than duplicating invite form logic in the toolbar.
- Topic publishing, reply publishing, and first-post edit errors with backend code `content_policy_violation` must use `shared/api/errors.contentPolicyMessage()` so the user sees a clear zh-CN safety prompt while drafts/edit text remain intact.

## Validation

- Run `pnpm --dir apps/web typecheck` after changing VM/API/query types.
- Run `pnpm --dir apps/web lint` after changing Vue templates or smoke specs.
- Smoke tests should click copy link, only-author, quote, code copy, edit, notification, search, and boards navigation with role/name selectors where possible.

## Content Safety Error Handling

### Signatures

- `contentPolicyMessage(error: unknown, fallback: string): string`
- Backend error code: `content_policy_violation`

### Contracts

- Do not inspect backend `details.fields` in components; use the stable error code only.
- Keep the authored draft or edit buffer unchanged when content safety rejects a write.
- Fallback messages still cover unauthenticated or network failures.

### Wrong vs Correct

#### Wrong

```ts
onError: () => setStatus("保存失败")
```

#### Correct

```ts
onError: (error) => {
  setStatus(contentPolicyMessage(error, "保存失败，请确认登录状态后重试"));
}
```

