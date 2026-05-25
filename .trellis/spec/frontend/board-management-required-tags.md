# Frontend Board Management, Required Tags, and Defaults Contract

## Scenario: Board settings UI, hierarchy display, scoped moderator management, and guided new-topic tags

### 1. Scope / Trigger

- Trigger: changing board directory/detail pages, board settings panels, board member role management, new-topic board templates, required tags, allowed tags, or default sort behavior.
- Applies to `features/boards/`, `pages/board/`, `pages/topic/NewTopicPage.vue`, `features/topics/`, shared query keys, router-linked board pages, and board styles.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Backend endpoint | Purpose |
|---|---|---|
| `fetchBoardSettings(slug)` | `GET /boards/{slug}/settings` | Load editable settings and members |
| `updateBoardSettings(slug, payload)` | `PUT /boards/{slug}/settings` | Save hierarchy/tag/template/defaults |
| `updateBoardMember(slug, username, payload)` | `PUT /boards/{slug}/members/{username}` | Promote/demote member |
| `removeBoardMember(slug, username)` | `DELETE /boards/{slug}/members/{username}` | Remove non-owner member |
| `useBoardSettings(slug, enabled)` | settings endpoint | Query wrapper |
| `useUpdateBoardSettings(slug)` | settings endpoint | Mutation + invalidation |
| `useUpdateBoardMember(slug)` | member endpoint | Mutation + invalidation |
| `useRemoveBoardMember(slug)` | member endpoint | Mutation + invalidation |

Board VM fields:

- `parentBoardId`, `parentBoardSlug`, `parentBoardName`
- `requiredTags`, `allowedTags`, `postTemplate`
- `defaultNotificationLevel`, `defaultSort`
- `childBoards` on board detail

### 3. Contracts

- `/boards` and board detail display child-board hierarchy using server-returned visible boards only.
- Board detail default sort uses `board.defaultSort` when the URL has no explicit `sort`.
- Board settings panel appears only for current board owner or admin; unauthorized users do not fire settings queries.
- Settings form preserves existing values while mutations are pending and shows typed backend errors.
- New-topic page:
  - preloads `selectedBoard.postTemplate` only when the editor body is empty;
  - shows required and allowed tag chips;
  - blocks publish when required tags are missing or allowed-tags policy is violated;
  - still relies on backend validation for the final source of truth.
- Query invalidation after settings/member mutations includes board detail, board list, board topics, and topic feeds where relevant.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Viewer is not owner/admin | No settings panel; no settings query |
| Settings save succeeds | Success copy; boards and detail queries refreshed |
| `required_tags_missing` on publish | Visible copy listing missing tags; draft remains |
| `tag_not_allowed` on publish | Visible copy listing disallowed tags; draft remains |
| Child boards returned | Render under parent board in directory and detail sidebar |
| No URL sort | Board page starts from `board.defaultSort` |
| Template board selected with empty body | Body is prefilled with board template |
| Template board selected after user typed content | Existing content is preserved |

### 5. Good/Base/Bad Cases

- Good: Board owner opens a settings panel with tag chips, template textarea, member role form, and child-board defaults in one focused card.
- Good: New-topic form shows “必填标签” chips that insert missing tags without hiding the free-form input.
- Base: A board with no required/allowed tags behaves like the current free-tag flow.
- Bad: Hard-coding board hierarchy client-side or decoding ownership from route params.

### 6. Tests Required

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- Manual smoke: `/boards` hierarchy, `/b/:slug` child boards/settings gated by owner/admin, `/new-topic` required tag guidance.

### 7. Wrong vs Correct

#### Wrong

```ts
const canManage = route.params.slug === "admin";
const childBoards = mockBoards.filter((board) => board.parent);
```

#### Correct

```ts
const canManage = computed(() => isAdmin(currentUser.value) || board.value?.ownerId === currentUser.value?.id);
const childBoards = computed(() => board.value?.childBoards ?? []);
```

