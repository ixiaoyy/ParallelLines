# Rich Composer, Onebox, Emoji, and Code UX

## Scenario: Composer Markdown tools, safe preview, drag upload, and link cards

### 1. Scope / Trigger

- Trigger: changing `features/topics/components/ComposerDrawer.vue`, composer Markdown utilities,
  upload insertion, onebox/link preview, emoji insertion, or composer code-block preview/copy behavior.
- Applies to topic and reply composer flows. The composer owns textarea cursor insertion and draft
  preservation; upload components/composables only return Markdown-safe upload references.

### 2. Signatures

UI helpers:

| Helper | Location | Return |
|---|---|---|
| `buildComposerPreview(rawMd)` | `features/topics/composerRichText.ts` | `{ html, oneboxes, codeBlocks, characterCount }` |
| `COMPOSER_EMOJI_OPTIONS` | `features/topics/composerRichText.ts` | custom shortcode/native emoji options |
| `CODE_LANGUAGE_OPTIONS` | `features/topics/composerRichText.ts` | language choices for fenced code blocks |
| `uploadErrorMessage(error)` | `features/uploads/errors.ts` | zh-CN upload failure copy |

Component contracts:

- `ComposerDrawer` still emits `submit(rawMd)` only after trimming non-empty content.
- `MarkdownUploadButton` emits `insert(markdown)` after upload succeeds.
- Drag/drop and paste upload use `useUploadFile()` and insert `toMarkdownUpload(upload, getApiUrl(upload.url))`.

### 3. Contracts

- Preview HTML is generated from escaped Markdown in `composerRichText.ts`; components may render that
  generated HTML with `v-html` but must not pass user-authored raw HTML through directly.
- Onebox cards are client-safe previews from detected `http(s)` URLs. They must dedupe URLs, skip
  direct media/archive file URLs, and safely degrade to host/path summary instead of fetching remote
  metadata from the browser.
- Image/file upload insertion must preserve the current draft and cursor selection; failed uploads only
  update visible status text.
- Code-block insertion uses fenced Markdown with the selected language. Preview code blocks expose
  `codeBlocks[]` so the component can copy exact raw code text without scraping rendered HTML.
- Custom emoji shortcodes such as `:parallel:` remain in raw Markdown while preview maps them to a
  display glyph.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Empty draft | Preview shows zh-CN placeholder; submit disabled |
| Toolbar wrap | Selected text is wrapped and selection remains around the authored text |
| Drag or paste image | File uploads through authenticated API, Markdown image/link is inserted at cursor |
| Upload rejected | Draft remains unchanged and `uploadErrorMessage()` shows size/type/auth-safe copy |
| Bare URL in draft | Onebox card appears with host/title/summary; direct file URLs do not create cards |
| Code block preview | Preview renders dark code block with language badge and copy button copies raw code |
| Custom emoji | Raw shortcode persists; preview displays mapped emoji glyph |

### 5. Good/Base/Bad Cases

- Good: keep preview parsing in `features/topics/composerRichText.ts` and keep component code focused
  on user actions, cursor insertion, and draft state.
- Good: reuse `useUploadFile()`, `toMarkdownUpload()`, and `getApiUrl()` for drag/paste uploads so
  auth headers and API-relative asset URLs stay consistent with `MarkdownUploadButton`.
- Base: Onebox preview shows a safe card using URL host and path when no remote metadata is available.
- Bad: using `fetch()` directly from the composer for uploads.
- Bad: rendering arbitrary raw Markdown/HTML from the textarea with `v-html` before escaping.
- Bad: replacing the full draft with uploaded Markdown and losing unsaved text.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- Focused manual/browser smoke when practical:
  - type text, use toolbar/emoji/code language selector, verify preview updates;
  - drag/paste an image while logged in, verify Markdown insertion and preview image;
  - paste a normal URL and verify safe onebox card; paste an image URL and verify no onebox card.

### 7. Wrong vs Correct

#### Wrong

```ts
const html = textarea.value;
preview.value = html;
await fetch('/api/v1/uploads', { method: 'POST', body: formData });
draft.value = markdown;
```

#### Correct

```ts
const preview = buildComposerPreview(draft.value);
const upload = await uploadMutation.mutateAsync({ file, kind: 'post_attachment' });
insertMarkdownUpload(toMarkdownUpload(upload, getApiUrl(upload.url)));
```
