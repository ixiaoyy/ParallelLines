from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.background_job import BackgroundJob
from app.models.interaction import Notification
from app.models.user import User
from app.services.background_jobs import BackgroundJobService
from app.services.email import clear_email_outbox, latest_email_secret
from app.workers.background_jobs import JOB_HANDLERS
from tests.helpers import get_test_database_url, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.asyncio
async def test_enqueue_idempotency_and_success_logs() -> None:
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        service = BackgroundJobService(session)
        first = await service.enqueue(
            "sample_task",
            payload={"value": 1},
            idempotency_key="sample:one",
        )
        second = await service.enqueue(
            "sample_task",
            payload={"value": 2},
            idempotency_key="sample:one",
        )
        assert second.id == first.id

        async def handler(
            _session: AsyncSession,
            payload: dict[str, object],
        ) -> dict[str, object]:
            return {"echo": payload["value"]}

        completed = await service.run_next(
            {"sample_task": handler},
            worker_id="test-worker",
        )
        assert completed is not None
        assert completed.id == first.id
        assert completed.status == "succeeded"
        assert completed.result == {"echo": 1}

        logs = await service.list_logs(first.id)
        assert [log.event for log in logs] == ["enqueued", "started", "succeeded"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_jobs_retry_then_dead_letter() -> None:
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        service = BackgroundJobService(session)
        job = await service.enqueue("always_fails", max_attempts=2)

        async def failing_handler(
            _session: AsyncSession,
            _payload: dict[str, object],
        ) -> dict[str, object]:
            raise RuntimeError("boom")

        first_attempt = await service.run_next(
            {"always_fails": failing_handler},
            worker_id="test-worker",
            retry_delay_seconds=0,
        )
        assert first_attempt is not None
        assert first_attempt.status == "queued"
        assert first_attempt.attempts == 1
        assert first_attempt.last_error == "boom"

        second_attempt = await service.run_next(
            {"always_fails": failing_handler},
            worker_id="test-worker",
            retry_delay_seconds=0,
        )
        assert second_attempt is not None
        assert second_attempt.status == "dead"
        assert second_attempt.attempts == 2
        assert second_attempt.finished_at is not None

        logs = await service.list_logs(job.id)
        assert [log.event for log in logs] == ["enqueued", "started", "retry", "started", "dead"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_scheduled_jobs_are_idempotent_per_time_bucket() -> None:
    session_factory, engine = await create_test_session()
    scheduled_at = datetime(2026, 5, 21, 12, 7, 30, tzinfo=UTC)

    async with session_factory() as session:
        service = BackgroundJobService(session)
        first = await service.enqueue_due_scheduled_jobs(
            background_hot_rank_interval_seconds=300,
            background_upload_cleanup_interval_seconds=3600,
            background_session_cleanup_interval_seconds=3600,
            background_digest_interval_seconds=3600,
            now=scheduled_at,
        )
        second = await service.enqueue_due_scheduled_jobs(
            background_hot_rank_interval_seconds=300,
            background_upload_cleanup_interval_seconds=3600,
            background_session_cleanup_interval_seconds=3600,
            background_digest_interval_seconds=3600,
            now=scheduled_at,
        )

        assert {job.id for job in first} == {job.id for job in second}
        job_count = await session.scalar(select(func.count(BackgroundJob.id)))
        assert job_count == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_notification_and_email_handlers_run_async() -> None:
    clear_email_outbox()
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        user = User(
            username="asyncuser",
            email="asyncuser@example.com",
            hashed_password="hashed",
            status="active",
        )
        session.add(user)
        await session.flush()
        service = BackgroundJobService(session)
        await service.enqueue_notification(
            user_id=user.id,
            kind="system",
            topic_id=None,
            post_id=None,
            actor_id=None,
            data={"message": "hello"},
            idempotency_key="notification:system:asyncuser",
        )
        await service.enqueue_email(
            kind="password_reset",
            to_email=user.email,
            username=user.username,
            secret="reset-token",
            idempotency_key="email:password-reset:asyncuser",
        )

        first = await service.run_next(
            JOB_HANDLERS,
            worker_id="test-worker",
            queues=("mail", "notifications"),
        )
        second = await service.run_next(
            JOB_HANDLERS,
            worker_id="test-worker",
            queues=("mail", "notifications"),
        )
        assert first is not None
        assert second is not None
        assert {first.status, second.status} == {"succeeded"}

        notification_count = await session.scalar(select(func.count(Notification.id)))
        assert notification_count == 1
        assert latest_email_secret("asyncuser@example.com", kind="password_reset") == "reset-token"

    await engine.dispose()
