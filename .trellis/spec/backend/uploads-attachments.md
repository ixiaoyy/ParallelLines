# Backend Uploads, Avatars, and Attachment Contract

## Scenario: Safe local uploads with post attachment ACL

### 1. Scope / Trigger

- Trigger: implementing or changing file upload, avatar upload, attachment references in
  Markdown, local/S3 storage configuration, or upload cleanup jobs.
- Applies to `apps/api/app/models/upload.py`, `schemas/uploads.py`, `services/uploads.py`,
  `api/v1/uploads.py`, `services/forum.py`, `workers/background_jobs.py`, and upload migrations.

### 2. Signatures

API endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/v1/uploads` multipart `file`, form `kind=post_attachment|avatar` | active user | Save one upload and return metadata/URL. |
| `POST /api/v1/uploads/avatar` multipart `file` | active user | Save avatar image, update `User.avatar_url`, return `UserPublic`. |
| `GET /api/v1/uploads/{upload_id}/content?download=false` | optional | Stream file content after avatar/public/private ACL checks. |
| `GET /api/v1/uploads/{upload_id}/thumbnail` | optional | Stream a cached WebP thumbnail after the same ACL checks as content. |

DB table:

- `uploads`: `user_id`, `board_id`, `topic_id`, `post_id`, `original_filename`,
  `storage_backend`, `storage_key`, `media_type`, `byte_size`, `sha256`, `kind`,
  `status`, `is_image`, `expires_at`, `deleted_at`, timestamps.

Settings:

- `UPLOAD_STORAGE_BACKEND=local|s3`
- `UPLOAD_STORAGE_PATH=var/uploads`
- `UPLOAD_CDN_BASE_URL`, `UPLOAD_S3_BUCKET`, `UPLOAD_S3_REGION`,
  `UPLOAD_S3_ENDPOINT_URL`
- `UPLOAD_MAX_BYTES`, `UPLOAD_MAX_AVATAR_BYTES`, `UPLOAD_MAX_FILES_PER_POST`
- `UPLOAD_TEMPORARY_TTL_HOURS`, `BACKGROUND_UPLOAD_CLEANUP_INTERVAL_SECONDS`

Service methods:

- `UploadService.create_post_upload(file, current_user) -> Upload`
- `UploadService.update_avatar(file, current_user) -> Upload`
- `UploadService.attach_uploads_to_post(raw_md, post, topic, board, current_user) -> None`
- `UploadService.get_upload_content(upload_id, current_user) -> UploadContent`
- `UploadService.get_upload_thumbnail(upload_id, current_user) -> UploadThumbnail`
- `UploadService.cleanup_expired_temporary_uploads() -> int`

CLI tools:

- `python -m app.migrate_uploads_to_s3 --dry-run|--apply`: migrate existing local upload objects
  to the configured S3-compatible backend while preserving `uploads.storage_key`.

### 3. Contracts

- Routers parse multipart input only; `UploadService` owns validation, disk writes,
  DB metadata, ACL checks, and cleanup.
- Upload URLs returned to clients are API-relative (`/uploads/{id}/content`); clients may
  convert them to absolute API URLs before inserting Markdown.
- `services/forum.py` must call `attach_uploads_to_post` after creating the first post,
  creating replies, and editing the topic first post. Attachments are discovered from
  Markdown URLs matching `/uploads/{id}/content` or `/api/v1/uploads/{id}/content`.
- Temporary post uploads start as `status="temporary"` and expire after
  `UPLOAD_TEMPORARY_TTL_HOURS`; attaching sets `status="attached"` and clears expiry.
- Avatar uploads must be images and set `status="avatar"`; `User.avatar_url` stores the
  API-relative content URL.
- Private-board attachments follow board visibility:
  - avatar: public;
  - temporary upload: owner only;
  - attached upload: readable only when the parent post/topic is visible and the current
    user can access the board;
  - deleted/hidden post or deleted upload: always `upload_not_found`.
- `GET /uploads/{id}/content` should set long-lived browser cache headers after ACL checks:
  anonymous-readable content uses public cache, authenticated reads use private cache, and
  `X-Content-Type-Options: nosniff` is sent with streamed files.
- `GET /uploads/{id}/thumbnail` follows the same privacy behavior as content, generates missing/stale
  thumbnails under `_thumbnails/` from the source image, returns WebP, and keeps thumbnail bounds small
  enough for page rails so clients do not preload full comic pages.
- Validation is based on server-side signature sniffing, not only browser MIME headers.
  Disallowed active types include `svg`, `html`, `js`, shell/PowerShell/batch scripts,
  PHP, DLL, COM, and EXE.
- Local storage paths are generated from server-assigned numeric upload IDs under UTC
  `YYYY/MM/` directories and must never accept user-provided path segments.
- Local-to-S3 migration must preserve the exact `storage_key` for original objects and existing
  cached thumbnails (`_thumbnails/{storage_key}.webp`), update `uploads.storage_backend` only after
  a successful write and read-back verification, and leave local files in place for rollback.
- The migration command defaults to dry-run and image rows only. Operators must pass `--apply` to
  change R2/S3 or database state, and may pass `--all-files` only when non-image attachments should
  also move.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| No auth uploads | `authentication_required` / 401 |
| Unsupported storage backend selected | `upload_storage_backend_unavailable` / 503 |
| Empty file | `upload_empty` / 422 |
| Exceeds configured size | `upload_too_large` / 422 with `max_bytes` |
| Disallowed extension/signature | `upload_type_not_allowed` / 422 |
| Declared MIME disagrees with sniffed content | `upload_mime_mismatch` / 422 |
| Avatar is not image | `avatar_must_be_image` / 422 |
| Markdown references another user's temporary upload | `upload_forbidden` / 403 |
| Markdown references missing/deleted upload | `upload_not_found` / 404 |
| Single post references too many uploads | `upload_count_exceeded` / 422 |
| Anonymous reads public-board attached image | 200 |
| Anonymous/stranger reads private-board attachment | `upload_not_found` / 404 |
| Accepted private-board member reads attachment | 200 |
| Local-to-S3 migration cannot read local source | Row remains `storage_backend="local"` and the script reports the missing object |
| Local-to-S3 migration verification fails | Row remains `storage_backend="local"` and the script exits non-zero in apply mode |

### 5. Good/Base/Bad Cases

- Good: upload image → insert `![diagram](https://api/api/v1/uploads/{id}/content)` →
  create topic → service attaches upload to first post → refreshed post renders `<img>`.
- Base: user uploads avatar with `POST /uploads/avatar`, then `/auth/me` and
  `/users/{username}` return the same `avatar_url`.
- Good: `python -m app.migrate_uploads_to_s3 --apply --limit 100` uploads originals and existing
  thumbnails using unchanged keys, then marks only successful rows as `storage_backend="s3"`.
- Bad: frontend hides the link to a private attachment but `GET /uploads/{id}/content`
  streams it to anonymous users.
- Bad: trusting `UploadFile.content_type == "image/png"` without checking PNG bytes.
- Bad: storing an absolute local path in `uploads.storage_key`.
- Bad: bulk-updating every upload row to `storage_backend="s3"` before all objects are verified in
  the bucket.

### 6. Tests Required

- `tests/test_uploads.py` must assert:
  - image upload attaches to topic first post and renders `<img>`;
  - content route returns original bytes for public attached uploads;
  - thumbnail route returns a cached WebP after ACL checks for public/private uploads;
  - disallowed extension, MIME mismatch, and oversize files return project error shape;
  - avatar upload updates `/auth/me` and public profile consistently;
  - private-board attachments are hidden from anonymous/stranger and visible after invite accept.
- Regression commands:
  - `ruff check app tests alembic`
  - `pytest -q --tb=short`
  - `python -m py_compile app/migrate_uploads_to_s3.py`
  - Alembic upgrade on a clean database through `0009_uploads`.

### 7. Wrong vs Correct

#### Wrong

```python
path = Path(settings.upload_storage_path) / file.filename
path.write_bytes(await file.read())
return {"url": f"/static/{file.filename}"}
```

#### Correct

```python
upload = await UploadService(session, settings).create_post_upload(file, current_user)
await session.commit()
return ApiResponse(data=UploadResponse.from_model(upload))
```

#### Wrong

```python
return FileResponse(upload.storage_key)
```

#### Correct

```python
content = await UploadService(session, settings).get_upload_content(upload_id, current_user)
return FileResponse(content.path, media_type=content.upload.media_type)
```
