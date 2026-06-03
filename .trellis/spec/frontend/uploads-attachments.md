# Frontend Uploads, Avatars, and Attachment Contract

## Scenario: Composer uploads and avatar update UI

### 1. Scope / Trigger

- Trigger: changing upload API wiring, Markdown insertion, composer attachment UI,
  avatar upload, or API-relative asset URL handling.
- Applies to `features/uploads/`, `pages/topic/NewTopicPage.vue`,
  `features/topics/components/ComposerDrawer.vue`, `pages/user/UserProfilePage.vue`,
  and `shared/api/client.ts`.

### 2. Signatures

API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `uploadFile(file, kind)` | `POST /uploads` multipart | `UploadResponse` |
| `uploadAvatar(file)` | `POST /uploads/avatar` multipart | `UserPublic` |

Types:

- `UploadResponse`: `id`, `url`, `original_filename`, `media_type`, `byte_size`,
  `kind`, `status`, `is_image`, `created_at`.
- `toMarkdownUpload(upload, absoluteUrl)` returns:
  - image: `![filename](absoluteUrl)`
  - file: `[filename](absoluteUrl)`

Helpers:

- `apiRequest` must not set `Content-Type: application/json` for `FormData`.
- `resolveApiAssetUrl(url)` converts `/uploads/...` and `/api/v1/...` to the configured
  `VITE_API_BASE_URL` origin for `<img>`/avatar display.
- Rendered post Markdown (`cooked_html`) must also resolve API-relative `<img src>` values
  before display; server-rendered `/uploads/...` paths cannot rely on the web host proxy.
- Post attachment image uploads may downscale large JPEG/PNG files client-side before `POST /uploads`,
  using a browser canvas and WebP output, but must fall back to the original file if encoding fails
  or the encoded blob is not smaller. GIF/WebP files are not transcoded so animation is not silently
  flattened.
- Client-side post image compression must preserve readable detail for comics and text-heavy images;
  avoid overly aggressive one-size-fits-all downscaling that makes speech bubbles or UI screenshots blurry.

Components/composables:

- `MarkdownUploadButton` emits `insert(markdown)` after upload succeeds.
- `useUploadFile()`
- `useUploadAvatar(() => username)`

### 3. Contracts

- Upload mutations must use `shared/api/client.ts` so auth tokens are attached.
- Composer components own cursor insertion; upload components only emit Markdown.
- Failed uploads never clear the current draft. Error text must explain login, type,
  MIME mismatch, or size failures.
- New topic and reply composers insert uploaded Markdown at the current cursor position
  with blank-line separation.
- Avatar upload is shown only for the current user's own profile; success invalidates
  `currentUser` and that user's profile query.
- Profile avatars must call `resolveApiAssetUrl(profile.avatar_url)` before passing to
  `UiAvatar`, because the backend stores API-relative URLs.
- Production upload flows must not use mock URLs or static fixtures.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Not logged in | Upload button reports failure and draft remains intact |
| Oversize file | Shows "文件超过当前上传大小限制" |
| Disallowed/mismatched file | Shows "文件类型不被允许，或内容与扩展名不一致" |
| Upload success in composer | Markdown is inserted into the textarea and draft autosave continues |
| Create topic/reply after upload | API persists raw Markdown with upload URL; refreshed post displays image/link |
| Avatar upload success | `/auth/me` cache and `/u/:username` profile show the new avatar |
| Avatar upload invalid type | Shows avatar-specific image-only error |

### 5. Good/Base/Bad Cases

- Good: `MarkdownUploadButton` uploads with `FormData`, emits Markdown, and the page inserts
  it without coupling the button to textarea refs.
- Base: user uploads avatar on their profile; the profile refetches and `UiAvatar` receives
  an API-absolute URL.
- Bad: component calls `fetch` directly, bypassing Authorization.
- Bad: manually setting `Content-Type: multipart/form-data`; the browser must include the
  boundary.
- Bad: replacing the entire composer draft after upload instead of cursor insertion.

### 6. Tests Required

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- Manual/browser checks:
  - login → upload image in new topic → publish → reload topic and image displays;
  - reply composer upload inserts Markdown without losing existing draft;
  - own profile avatar upload updates profile and current-user cache.

### 7. Wrong vs Correct

#### Wrong

```ts
await fetch("/api/v1/uploads", { method: "POST", body: formData });
draft.value = markdown;
```

#### Correct

```ts
const upload = await uploadMutation.mutateAsync({ file, kind: "post_attachment" });
emit("insert", toMarkdownUpload(upload, getApiUrl(upload.url)));
```
