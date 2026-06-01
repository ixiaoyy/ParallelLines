# Rich Composer Contract

## Scenario: md-editor-v3 composer, safe preview, uploads, and no explanatory helper copy

### 1. Scope / Trigger

- Trigger: changing `features/topics/components/ComposerDrawer.vue`, `pages/topic/NewTopicPage.vue`, upload insertion, editor toolbar options, draft preservation, or Markdown preview sanitization.
- Applies to topic and reply composer flows. Both flows use `md-editor-v3` for Markdown editing and still submit the backend `raw_md` string.
- Product decision: composer UI must not show explanatory helper/status copy, custom side preview placeholders, onebox explanations, or long upload instructions. Keep only labels, actions, validation/errors, and action-triggered upload status.

### 2. Signatures

Component contracts:

| Contract | Location | Notes |
|---|---|---|
| `submit(rawMd)` | `ComposerDrawer.vue` | Emitted only after trimming non-empty content. |
| `raw_md` create payload | `NewTopicPage.vue` | Sends trimmed Markdown body. |
| `MarkdownUploadButton` | `features/uploads/components/MarkdownUploadButton.vue` | Emits `insert(markdown)` after upload succeeds; composers append the Markdown to the current draft/body. |
| `md-editor-v3 @onUploadImg` | composer components | Uses `useUploadFile()` and passes absolute URLs back to editor callback. |
| `sanitizeEditorHtml(html)` | composer components | Runs `DOMPurify.sanitize()` for md-editor preview HTML. |

### 3. Contracts

- The editor source of truth is the Markdown string (`draft` for replies, `body` for new topics); do not introduce a parallel custom preview state.
- md-editor preview HTML must be sanitized with DOMPurify before rendering.
- Uploads must reuse `useUploadFile()` and `getApiUrl()` so auth headers and API-relative asset URLs stay consistent.
- The external attachment button remains available for non-image files; the editor image toolbar handles image uploads through the same upload mutation.
- Topic/reply composers should use concise placeholders (`正文`, `输入回复内容`, etc.) and must not add explanatory paragraphs, draft-version badges, or empty preview hint cards.
- Validation and error messages are allowed because they are actionable; decorative/help copy is not.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Empty draft/body | Submit disabled for replies; new-topic validation blocks publish. |
| Editor toolbar action | Markdown updates inside md-editor without custom toolbar state. |
| Editor image upload | File uploads through authenticated API and editor callback inserts image Markdown. |
| Attachment upload | Non-image attachment Markdown is appended without replacing existing content. |
| Upload rejected | Existing content remains visible and `uploadErrorMessage()` is shown. |
| Preview toggled | Preview renders sanitized HTML; unsafe raw HTML is stripped. |
| Old helper copy regression | Browser smoke must not find removed helper, draft-version, preview-heading, or empty-preview copy. |

### 5. Good/Base/Bad Cases

- Good: use `md-editor-v3` toolbar + DOMPurify instead of rebuilding Markdown toolbar, onebox cards, emoji picker, and preview panes in app code.
- Good: keep upload paths on existing upload composables/API helpers.
- Base: append external attachment Markdown when direct cursor insertion is not exposed by the editor wrapper.
- Bad: reintroducing explanatory helper paragraphs or draft-version status text in the composer chrome.
- Bad: rendering arbitrary Markdown/HTML preview output without sanitization.
- Bad: importing Node-oriented sanitizer packages that Vite must externalize for browser use.

### 6. Tests Required

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- Focused browser smoke when practical:
  - open a topic detail, verify reply composer renders md-editor and old helper strings are absent;
  - open new-topic page, verify editor uses md-editor and no explanatory editor copy is visible;
  - type Markdown, toggle preview, and try image/attachment upload while logged in when upload credentials are available.
