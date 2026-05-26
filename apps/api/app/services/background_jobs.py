from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.background_job import BackgroundJob, BackgroundJobLog

BackgroundJobHandler = Callable[
    [AsyncSession, dict[str, object]], Awaitable[dict[str, object] | None]
]

ACTIVE_JOB_STATUSES = {"queued", "running"}
TERMINAL_JOB_STATUSES = {"succeeded", "dead"}


class BackgroundJobService:
    """Database-backed queue used by the single project worker runtime."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        task_name: str,
        *,
        payload: dict[str, object] | None = None,
        queue: str = "default",
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
        priority: int = 100,
        max_attempts: int = 3,
        commit: bool = True,
    ) -> BackgroundJob:
        if idempotency_key:
            existing = await self.session.scalar(
                select(BackgroundJob).where(BackgroundJob.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return existing

        job = BackgroundJob(
            queue=queue,
            task_name=task_name,
            payload=payload or {},
            status="queued",
            idempotency_key=idempotency_key,
            priority=priority,
            run_at=_queue_timestamp(run_at or utcnow()),
            attempts=0,
            max_attempts=max_attempts,
        )
        self.session.add(job)
        await self.session.flush()
        self._add_log(
            job.id,
            event="enqueued",
            message="Job queued",
            data={"queue": queue, "task_name": task_name},
        )
        if commit:
            await self.session.commit()
            await self.session.refresh(job)
        return job

    async def enqueue_email(
        self,
        *,
        kind: str,
        to_email: str,
        username: str,
        secret: str,
        idempotency_key: str,
        commit: bool = True,
    ) -> BackgroundJob:
        return await self.enqueue(
            "send_email",
            queue="mail",
            payload={
                "kind": kind,
                "to_email": to_email,
                "username": username,
                "secret": secret,
            },
            idempotency_key=idempotency_key,
            priority=20,
            max_attempts=5,
            commit=commit,
        )

    async def enqueue_notification(
        self,
        *,
        user_id: str,
        kind: str,
        topic_id: str | None,
        post_id: str | None,
        actor_id: str | None,
        data: dict[str, object],
        idempotency_key: str | None = None,
        commit: bool = True,
    ) -> BackgroundJob | None:
        if actor_id and user_id == actor_id:
            return None
        payload: dict[str, object] = {
            "user_id": user_id,
            "kind": kind,
            "data": data,
        }
        if topic_id is not None:
            payload["topic_id"] = topic_id
        if post_id is not None:
            payload["post_id"] = post_id
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return await self.enqueue(
            "create_notification",
            queue="notifications",
            payload=payload,
            idempotency_key=idempotency_key,
            priority=30,
            commit=commit,
        )

    async def acquire_next(
        self,
        *,
        worker_id: str,
        queues: Sequence[str] = ("default",),
        now: datetime | None = None,
    ) -> BackgroundJob | None:
        run_time = _queue_timestamp(now or utcnow())
        statement = select(BackgroundJob).where(
            BackgroundJob.status == "queued",
            BackgroundJob.run_at <= run_time,
        )
        if queues:
            statement = statement.where(BackgroundJob.queue.in_(tuple(queues)))
        job = await self.session.scalar(
            statement.order_by(
                BackgroundJob.priority.asc(),
                BackgroundJob.run_at.asc(),
                BackgroundJob.created_at.asc(),
            ).limit(1)
        )
        if job is None:
            return None

        job.status = "running"
        job.locked_at = run_time
        job.locked_by = worker_id
        job.attempts += 1
        self._add_log(
            job.id,
            event="started",
            message="Job started",
            data={"attempt": job.attempts, "worker_id": worker_id},
        )
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def run_next(
        self,
        handlers: dict[str, BackgroundJobHandler],
        *,
        worker_id: str,
        queues: Sequence[str] = ("default",),
        retry_delay_seconds: int = 60,
    ) -> BackgroundJob | None:
        job = await self.acquire_next(worker_id=worker_id, queues=queues)
        if job is None:
            return None

        handler = handlers.get(job.task_name)
        if handler is None:
            return await self._mark_dead(job.id, f"Unknown task handler: {job.task_name}")

        try:
            result = await handler(self.session, dict(job.payload or {}))
        except Exception as exc:
            return await self._mark_retry_or_dead(
                job.id,
                error=str(exc) or type(exc).__name__,
                retry_delay_seconds=retry_delay_seconds,
            )

        finished_at = _queue_timestamp(utcnow())
        job.status = "succeeded"
        job.result = result or {}
        job.finished_at = finished_at
        job.locked_at = None
        job.locked_by = None
        job.last_error = None
        self._add_log(
            job.id,
            event="succeeded",
            message="Job succeeded",
            data={"attempt": job.attempts},
        )
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[BackgroundJob]:
        statement = select(BackgroundJob).order_by(desc(BackgroundJob.created_at)).limit(limit)
        if status:
            statement = statement.where(BackgroundJob.status == status)
        return list(await self.session.scalars(statement))

    async def list_logs(self, job_id: str) -> list[BackgroundJobLog]:
        return list(
            await self.session.scalars(
                select(BackgroundJobLog)
                .where(BackgroundJobLog.job_id == job_id)
                .order_by(BackgroundJobLog.created_at.asc())
            )
        )

    async def queue_summary(self) -> dict[str, object]:
        rows = (
            await self.session.execute(
                select(BackgroundJob.status, func.count(BackgroundJob.id)).group_by(
                    BackgroundJob.status
                )
            )
        ).all()
        counts = {str(status): int(count) for status, count in rows}
        return {
            "counts": counts,
            "active": sum(counts.get(status, 0) for status in ACTIVE_JOB_STATUSES),
            "terminal": sum(counts.get(status, 0) for status in TERMINAL_JOB_STATUSES),
        }

    async def enqueue_due_scheduled_jobs(
        self,
        *,
        background_hot_rank_interval_seconds: int,
        background_upload_cleanup_interval_seconds: int,
        background_session_cleanup_interval_seconds: int,
        background_digest_interval_seconds: int,
        now: datetime | None = None,
    ) -> list[BackgroundJob]:
        run_time = _queue_timestamp(now or utcnow())
        jobs: list[BackgroundJob] = []
        schedules = (
            ("recompute_hot_scores", background_hot_rank_interval_seconds),
            ("cleanup_expired_uploads", background_upload_cleanup_interval_seconds),
            ("cleanup_expired_sessions", background_session_cleanup_interval_seconds),
            ("send_digest_emails", background_digest_interval_seconds),
        )
        for task_name, interval_seconds in schedules:
            if interval_seconds <= 0:
                continue
            bucket = _schedule_bucket(run_time, interval_seconds)
            jobs.append(
                await self.enqueue(
                    task_name,
                    queue="maintenance",
                    payload={"bucket": bucket.isoformat(), "scheduled_at": run_time.isoformat()},
                    idempotency_key=f"scheduled:{task_name}:{int(bucket.timestamp())}",
                    run_at=run_time,
                    priority=200,
                    commit=False,
                )
            )
        await self.session.commit()
        return jobs

    async def _mark_retry_or_dead(
        self,
        job_id: str,
        *,
        error: str,
        retry_delay_seconds: int,
    ) -> BackgroundJob:
        await self.session.rollback()
        job = await self._require_job(job_id)
        error_summary = error[:1000]
        now = _queue_timestamp(utcnow())
        job.last_error = error_summary
        job.locked_at = None
        job.locked_by = None
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.run_at = _queue_timestamp(
                now + timedelta(seconds=max(retry_delay_seconds, 0) * max(job.attempts, 1))
            )
            self._add_log(
                job.id,
                event="retry",
                message="Job failed and was queued for retry",
                data={
                    "attempt": job.attempts,
                    "error": error_summary,
                    "run_at": job.run_at.isoformat(),
                },
            )
        else:
            job.status = "dead"
            job.finished_at = now
            self._add_log(
                job.id,
                event="dead",
                message="Job exhausted retries and entered dead letter state",
                data={"attempt": job.attempts, "error": error_summary},
            )
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def _mark_dead(self, job_id: str, error: str) -> BackgroundJob:
        job = await self._require_job(job_id)
        job.status = "dead"
        job.last_error = error[:1000]
        job.finished_at = _queue_timestamp(utcnow())
        job.locked_at = None
        job.locked_by = None
        self._add_log(
            job.id,
            event="dead",
            message="Job moved to dead letter state",
            data={"attempt": job.attempts, "error": job.last_error or ""},
        )
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def _require_job(self, job_id: str) -> BackgroundJob:
        job = await self.session.get(BackgroundJob, job_id)
        if job is None:
            raise RuntimeError(f"Background job not found: {job_id}")
        return job

    def _add_log(
        self,
        job_id: str,
        *,
        event: str,
        message: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            BackgroundJobLog(
                job_id=job_id,
                event=event,
                message=message,
                data=data,
                created_at=_queue_timestamp(utcnow()),
            )
        )


def _queue_timestamp(value: datetime) -> datetime:
    """Normalize queue timestamps to MySQL DATETIME second precision.

    MySQL DATETIME columns in this schema do not persist fractional seconds. If an immediate
    `run_at` is inserted with microseconds, MySQL can round it into the next second, making a job
    appear not due to a worker that polls in the same second. The queue only promises second-level
    scheduling, so floor values before persisting or comparing them.
    """

    return value.replace(microsecond=0)


def _schedule_bucket(now: datetime, interval_seconds: int) -> datetime:
    aware_now = now if now.tzinfo else now.replace(tzinfo=UTC)
    epoch_seconds = int(aware_now.timestamp())
    bucket_epoch = epoch_seconds - (epoch_seconds % interval_seconds)
    return datetime.fromtimestamp(bucket_epoch, UTC)
