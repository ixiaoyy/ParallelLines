# Backend Backup, Restore Validation, and Data Export Contract

## Scenario: Admin disaster archive and safe user/site exports

### 1. Scope / Trigger

- Trigger: changing backup artifact storage, admin backup APIs, restore validation,
  personal data export, all-site export, or backup worker handlers.
- Applies to `app/models/backup.py`, `schemas/backups.py`, `services/backups.py`,
  `api/v1/admin.py`, `api/v1/users.py`, `workers/background_jobs.py`,
  `alembic/versions/*backup*`, `docker-compose.yml`, and operations docs.

### 2. Signatures

Admin APIs:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/admin/backups` | admin | Create `backup_artifacts` row and enqueue `create_site_backup`. |
| `GET` | `/api/v1/admin/backups?status=&limit=` | admin | List backup artifacts newest first. |
| `GET` | `/api/v1/admin/backups/{backup_id}` | admin | Read one artifact status/checksum. |
| `GET` | `/api/v1/admin/backups/{backup_id}/download` | admin | Download succeeded ZIP; sends `X-Backup-SHA256`. |
| `DELETE` | `/api/v1/admin/backups/{backup_id}` | admin | Delete local archive and mark artifact `deleted`. |
| `POST` | `/api/v1/admin/backups/{backup_id}/restore` | admin | Validate checksum after exact confirmation. |
| `GET` | `/api/v1/admin/exports/site` | admin | Download a redacted full-site JSON ZIP export. |

User API:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/users/me/export` | active user | Download own profile/topics/posts/actions ZIP export. |

DB table:

- `backup_artifacts`: `kind`, `status`, `filename`, `storage_backend`,
  `storage_key`, `byte_size`, `sha256`, `metadata`, `failure_reason`,
  `created_by_id`, `completed_at`, timestamps.

Worker handler:

- `create_site_backup` on the unified `app.workers.background_jobs` worker.

Runtime env:

- `BACKUP_STORAGE_PATH`: local directory shared by API and worker for generated ZIPs.

### 3. Contracts

- All `/admin/backups*` and `/admin/exports/site` endpoints must require admin role and
  return `admin_required` / 403 for ordinary users.
- `POST /admin/backups` must not generate the archive on the request path; it writes
  a queued artifact, audit log `backup_requested`, and background job with
  payload `{ "backup_id": "<uuid>" }`.
- Backup archives are local ZIP files containing `metadata.json`, `database/*.json`,
  and optionally `uploads/**` when `include_uploads=true`.
- Backup and export JSON must redact keys/columns containing password/token/secret/code,
  including `hashed_password`, `token_hash`, `refresh_token_hash`, and job payload secrets.
- Download is allowed only when `backup_artifacts.status == "succeeded"` and the local
  file exists; otherwise return `backup_not_ready` or `backup_file_not_found`.
- Failed generation must set artifact `status="failed"`, `failure_reason`, and rely on
  background job logs for retry/dead-letter details.
- Restore endpoint is intentionally non-destructive in this project phase: it requires
  exact confirmation `RESTORE {backup_id}`, rejects production, verifies the checksum,
  writes audit log `backup_restore_validated`, and returns `restore_supported=false`.
- Docker Compose must mount the same `backup-data` volume into API and worker; mismatched
  paths produce archives the API cannot download.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Non-admin creates/lists/downloads backup | `admin_required` / 403 |
| Backup is queued/running/failed/deleted and download is requested | `backup_not_ready` / 422 |
| Backup DB row exists but local file is absent | `backup_file_not_found` / 404 |
| Wrong restore confirmation | `invalid_restore_confirmation` / 422 |
| Restore validation in production | `restore_forbidden_in_production` / 403 |
| Checksum mismatch | `backup_checksum_mismatch` / 422 |
| Backup worker cannot write archive | artifact `failed`, job `dead`, failure log exists |
| User export requested by active user | ZIP contains own profile/content and no secrets |
| Site export requested by admin | ZIP contains redacted database JSON and checksum header |

### 5. Good/Base/Bad Cases

- Good: admin creates backup, worker succeeds, admin downloads ZIP and verifies
  `X-Backup-SHA256` before moving it off-host.
- Base: ordinary user downloads `/users/me/export` and sees their own posts/actions,
  not password hashes or token rows.
- Bad: API creates large ZIP synchronously inside `POST /admin/backups`.
- Bad: worker writes to `/var/backups` while API reads `/var/lib/parallellines/backups`.
- Bad: export includes `background_jobs.payload.secret` or `users.hashed_password` raw value.

### 6. Tests Required

- `tests/test_backups.py` must assert:
  - non-admin cannot create/download full backup;
  - backup job generates succeeded artifact, checksum, downloadable ZIP, and restore validation;
  - failed backup marks artifact failed and job log enters dead-letter;
  - user export and site export redact password/token/secret/code fields.
- Full backend gate: `ruff check app tests alembic` and `pytest -q`.
- Config gate after Compose/env changes: `docker compose config --quiet`.

### 7. Wrong vs Correct

#### Wrong

```python
@router.post("/admin/backups")
async def backup_now(...):
    return ZipFile("/tmp/site.zip", "w")  # request path does heavy work
```

#### Correct

```python
artifact = BackupArtifact(status="queued", ...)
await BackgroundJobService(session).enqueue(
    "create_site_backup",
    queue="maintenance",
    payload={"backup_id": artifact.id},
    commit=False,
)
```
