# Backend Background Jobs Contract

## Scenario: Unified async queue, worker runtime, and scheduled maintenance jobs

### 1. Scope / Trigger

- Trigger: adding or changing async mail delivery, notification fan-out, scheduled maintenance, backup generation, search index rebuilds, retry/dead-letter handling, or worker deployment.
- Applies to `app/models/background_job.py`, `app/services/background_jobs.py`, `app/workers/background_jobs.py`, `api/v1/admin.py`, `schemas/admin.py`, backup services, Alembic migrations, and `docker-compose.yml` worker commands.
- This project is still in active development: do **not** preserve old standalone worker entrypoints when the unified worker replaces them.

### 2. Signatures

Database tables:

| Table | Fields | Contract |
|---|---|---|
| `background_jobs` | `queue`, `task_name`, `payload`, `status`, `idempotency_key`, `priority`, `run_at`, `attempts`, `max_attempts`, `locked_at`, `locked_by`, `last_error`, `result`, `finished_at` | Durable queue, retry state, and dead-letter record |
| `background_job_logs` | `job_id`, `event`, `message`, `data`, `created_at` | Append-only operational log for enqueue/start/success/retry/dead events |

Service signatures:

- `BackgroundJobService.enqueue(task_name, payload=None, queue="default", idempotency_key=None, run_at=None, priority=100, max_attempts=3, commit=True) -> BackgroundJob`
- `BackgroundJobService.run_next(handlers, worker_id, queues=("default",), retry_delay_seconds=60) -> BackgroundJob | None`
- `BackgroundJobService.enqueue_due_scheduled_jobs(background_hot_rank_interval_seconds, background_upload_cleanup_interval_seconds, background_session_cleanup_interval_seconds, background_digest_interval_seconds, background_frontier_news_interval_seconds=0, background_living_forum_interval_seconds=0, now=None) -> list[BackgroundJob]`
- `BackgroundJobService.list_jobs(status=None, limit=50) -> list[BackgroundJob]`
- `BackgroundJobService.list_logs(job_id) -> list[BackgroundJobLog]`

Worker command:

```bash
python -m app.workers.background_jobs
```

Admin APIs:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/admin/background-jobs?status=&limit=` | Admin-only queue inspection |
| `GET` | `/api/v1/admin/background-jobs/{job_id}/logs` | Admin-only per-job event log |
| `GET` | `/api/v1/admin/system` | Includes queue counts and unified worker config |

Runtime env:

| Env | Purpose |
|---|---|
| `BACKGROUND_JOB_POLL_SECONDS` | Worker sleep between polling loops |
| `BACKGROUND_JOB_BATCH_SIZE` | Max jobs processed per worker loop |
| `BACKGROUND_JOB_RETRY_DELAY_SECONDS` | Base retry delay; multiplied by attempt count |
| `BACKGROUND_HOT_RANK_INTERVAL_SECONDS` | Scheduled hot-score recompute bucket size |
| `BACKGROUND_UPLOAD_CLEANUP_INTERVAL_SECONDS` | Scheduled temporary upload cleanup bucket size |
| `BACKGROUND_SESSION_CLEANUP_INTERVAL_SECONDS` | Scheduled expired session cleanup bucket size |
| `BACKGROUND_DIGEST_INTERVAL_SECONDS` | Scheduled email digest dispatcher bucket size |
| `BACKGROUND_LIVING_FORUM_INTERVAL_SECONDS` | Scheduled living-forum daily program bucket size; `0` disables enqueueing |
| `FRONTIER_NEWS_REQUEST_TIMEOUT_SECONDS` | Per-request timeout for frontier upstream RSS/API fetches |

Frontier source `config` keys:

| Key | Purpose |
|---|---|
| `max_items` | Candidate window fetched from the upstream source before de-duplication |
| `review_batch_size` | Maximum new `frontier_news` reviewables to enqueue per source in one collection pass; default is 3 |
| `candidate_items` | Hacker News top-story scan window before AI keyword filtering |
| `candidate_links` | HTML news-index link scan window before AI keyword filtering |
| `allowed_hosts` | Host allow-list for generic HTML news-index sources; required for broad media sites |
| `link_contains` | URL/path fragments that candidate news-index links must contain |
| `arxiv_category_items` | Optional per-category arXiv result count; absent values are derived from `max_items` |

Frontier source `kind` values:

| Kind | Purpose |
|---|---|
| `rss` | RSS/Atom feeds with standard item/entry nodes |
| `arxiv` | arXiv Atom API category queries |
| `hacker_news` | Hacker News top story API filtered by AI keywords |
| `github_search` | GitHub repository search API |
| `xai_news` | xAI public news HTML index plus announcement detail pages |
| `arena_leaderboard` | Arena.ai leaderboard pages converted into benchmark news entries |
| `news_html_index` | Trusted media-site HTML indexes restricted by host/path config, then filtered by AI keywords |

### 3. Contracts

- The unified worker owns all backend async work: mail delivery, notification creation, digest dispatch, hot-score recompute, search index rebuilds, temporary upload cleanup, and stale session cleanup.
- The unified worker also owns living-forum daily program publishing and persona reply engagement through `publish_living_forum_day`; do not add a standalone daemon for AI-operated programs.
- Site backup generation is also a unified worker task via `create_site_backup`; admin request handlers only enqueue it.
- Do not add new `app/workers/<single-purpose>.py` daemons or Compose services for background work; add a handler to `JOB_HANDLERS` instead.
- `idempotency_key` is globally unique when non-null. Re-enqueueing the same key returns the existing row and must not duplicate side effects.
- Handler payloads must be small JSON dictionaries. They must not contain passwords or large rendered bodies; auth email jobs may contain the one-time email secret needed to deliver that message.
- Request-path services that enqueue work inside their own transaction must pass `commit=False` and let the caller commit once.
- Worker handlers must be idempotent or protected by an idempotency key because a side effect can happen before final job status commit.
- Failed jobs return to `queued` while `attempts < max_attempts`; after the final attempt they move to `dead` with `finished_at` and `last_error`.
- Scheduled jobs use time-bucketed idempotency keys: repeated worker loops in the same bucket must produce one queue row.
- Frontier news collection enqueues only a small per-source review batch per pass, so one noisy
  source cannot flood the unified moderation queue. Failed source fetches keep their previous
  `last_checked_at` and set `last_error`, allowing the next scheduled bucket to retry instead of
  waiting the full source interval.
- Frontier news drafts are flash-news style: the generated `raw_md` starts with a controlled
  `:::news-card` block containing source metadata, optional image, original-title link, and
  a concise summary. If no image can be extracted, the card must still include title and
  summary. Do not append generic generated `一句话` explanations or moderation/process wording.
  Generated topic tags include `前沿资讯` and content tags; do not add a `转载` tag by default.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Duplicate `idempotency_key` | Return existing job; no duplicate queue row |
| Handler succeeds | Job status `succeeded`, result JSON stored, `succeeded` log appended |
| Handler raises and attempts remain | Job status `queued`, future `run_at`, `retry` log appended |
| Handler raises on final attempt | Job status `dead`, `finished_at` set, `dead` log appended |
| Unknown `task_name` | Job moves to `dead` with `Unknown task handler` error |
| Worker loop called repeatedly in one schedule bucket | One scheduled row per task and bucket |
| `rebuild_search_index` handler succeeds | Non-hidden topics have `search_documents`; stale docs are removed |
| Backup archive generation fails | Job enters retry/dead-letter and `backup_artifacts.status` becomes `failed` |
| Non-admin queries queue APIs | `403 admin_required` |
| Missing job logs route target | `404 background_job_not_found` |

### 5. Good/Base/Bad Cases

- Good: `ForumService` enqueues `create_notification` jobs with `commit=False`; notification rows appear only after the worker processes the queue.
- Good: auth reset/email-change requests enqueue `send_email` and return a uniform API response without doing SMTP work in the request path.
- Base: local Docker Compose runs only `worker: python -m app.workers.background_jobs` for every background task.
- Bad: keeping `app.workers.hot_ranking` or `app.workers.upload_cleanup` as runnable compatibility entrypoints after the unified worker exists.
- Bad: logging email reset tokens or storing passwords in `background_job_logs.data`.

### 6. Tests Required

- `tests/test_background_jobs.py` must cover:
  - enqueue idempotency returning the same row;
  - success status and enqueue/start/succeeded logs;
  - retry then dead-letter transition;
  - scheduled time-bucket idempotency;
  - async notification and email handlers.
- Existing auth tests that inspect memory email outbox must drain background jobs before reading the outbox.
- Existing notification tests must drain background jobs before asserting readable notification rows.
- Deployment validation must run `docker compose config` after worker/env changes.

### 7. Wrong vs Correct

#### Wrong

```yaml
worker:
  command: python -m app.workers.hot_ranking
upload-cleanup-worker:
  command: python -m app.workers.upload_cleanup
```

#### Correct

```yaml
worker:
  command: python -m app.workers.background_jobs
```

#### Wrong

```python
# Sends mail synchronously inside the request transaction.
await EmailService(settings).send_password_reset(to_email=user.email, username=user.username, token=token)
```

#### Correct

```python
await BackgroundJobService(session).enqueue_email(
    kind="password_reset",
    to_email=user.email,
    username=user.username,
    secret=token,
    idempotency_key=f"email:password_reset:{token_hash}",
    commit=False,
)
```
