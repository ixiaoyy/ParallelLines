from __future__ import annotations

import asyncio
import socket
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.db.base import utcnow
from app.db.session import AsyncSessionLocal
from app.models.forum import Topic
from app.models.interaction import Notification
from app.models.user import UserSession
from app.services.background_jobs import BackgroundJobHandler, BackgroundJobService
from app.services.backups import BackupService
from app.services.email import EmailService
from app.services.email_notifications import EmailNotificationService
from app.services.forum import calculate_hot_score
from app.services.frontier_news import FrontierNewsService
from app.services.integrations import IntegrationService
from app.services.search import SearchIndexService
from app.services.uploads import UploadService


async def recompute_hot_scores(session: AsyncSession) -> int:
    """Recompute deterministic hot scores for all non-deleted topics."""

    topics = list(await session.scalars(select(Topic).where(Topic.deleted_at.is_(None))))
    for topic in topics:
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
    await session.flush()
    return len(topics)


async def handle_recompute_hot_scores(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    return {"updated_count": await recompute_hot_scores(session)}


async def handle_cleanup_expired_uploads(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    settings = get_settings()
    deleted_count = await UploadService(session, settings).cleanup_expired_temporary_uploads()
    return {"deleted_count": deleted_count}


async def handle_cleanup_expired_sessions(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    settings = get_settings()
    now = utcnow()
    cutoff = now - timedelta(days=settings.refresh_token_days)
    sessions = list(
        await session.scalars(
            select(UserSession).where(
                UserSession.revoked_at.is_(None),
                UserSession.last_seen_at < cutoff,
            )
        )
    )
    for user_session in sessions:
        user_session.revoked_at = now
    await session.flush()
    return {"revoked_count": len(sessions)}


async def handle_create_notification(
    session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    user_id = _payload_str(payload, "user_id")
    kind = _payload_str(payload, "kind")
    actor_id = _payload_optional_str(payload, "actor_id")
    if actor_id and actor_id == user_id:
        return {"skipped": True, "reason": "self_notification"}

    notification = Notification(
        user_id=user_id,
        type=kind,
        topic_id=_payload_optional_str(payload, "topic_id"),
        post_id=_payload_optional_str(payload, "post_id"),
        actor_id=actor_id,
        data=_payload_dict(payload, "data"),
    )
    session.add(notification)
    await session.flush()
    await EmailNotificationService(session).enqueue_notification_email(notification, commit=False)
    return {"notification_id": notification.id}


async def handle_send_notification_email(
    session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    return await EmailNotificationService(session).send_notification_email(
        _payload_str(payload, "notification_id")
    )


async def handle_send_digest_emails(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    return await EmailNotificationService(session).send_digest_emails()


async def handle_send_email(
    _session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    settings = get_settings()
    service = EmailService(settings)
    kind = _payload_str(payload, "kind")
    to_email = _payload_str(payload, "to_email")
    username = _payload_str(payload, "username")
    secret = _payload_str(payload, "secret")

    if kind == "email_verification":
        await service.send_verification_code(to_email=to_email, username=username, code=secret)
    elif kind == "password_reset":
        await service.send_password_reset(to_email=to_email, username=username, token=secret)
    elif kind == "email_change":
        await service.send_email_change(to_email=to_email, username=username, token=secret)
    else:
        raise AppError("unknown_email_kind", "Unknown email kind", status_code=422)
    return {"kind": kind, "to_email_domain": to_email.rsplit("@", 1)[-1]}


async def handle_create_site_backup(
    session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    return await BackupService(session).run_site_backup(_payload_str(payload, "backup_id"))


async def handle_rebuild_search_index(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    return await SearchIndexService(session).rebuild_all()


async def handle_deliver_webhook(
    session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    return await IntegrationService(session).deliver_webhook(_payload_str(payload, "delivery_id"))


async def handle_collect_frontier_news(
    session: AsyncSession,
    _payload: dict[str, object],
) -> dict[str, object]:
    """Collect frontier news in the unified worker and enqueue AI-prepared reviewables."""

    result = await FrontierNewsService(session).collect_due_sources()
    return result.model_dump()


JOB_HANDLERS: dict[str, BackgroundJobHandler] = {
    "recompute_hot_scores": handle_recompute_hot_scores,
    "cleanup_expired_uploads": handle_cleanup_expired_uploads,
    "cleanup_expired_sessions": handle_cleanup_expired_sessions,
    "create_notification": handle_create_notification,
    "send_notification_email": handle_send_notification_email,
    "send_digest_emails": handle_send_digest_emails,
    "send_email": handle_send_email,
    "create_site_backup": handle_create_site_backup,
    "rebuild_search_index": handle_rebuild_search_index,
    "deliver_webhook": handle_deliver_webhook,
    "collect_frontier_news": handle_collect_frontier_news,
}

WORKER_QUEUES = ("mail", "notifications", "maintenance", "webhooks", "default")


async def run_once(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    settings: Settings | None = None,
    worker_id: str | None = None,
    queues: Sequence[str] = WORKER_QUEUES,
    enqueue_scheduled: bool = True,
) -> int:
    runtime_settings = settings or get_settings()
    factory = session_factory or AsyncSessionLocal
    processed_count = 0
    async with factory() as session:
        service = BackgroundJobService(session)
        if enqueue_scheduled:
            await service.enqueue_due_scheduled_jobs(
                background_hot_rank_interval_seconds=(
                    runtime_settings.background_hot_rank_interval_seconds
                ),
                background_upload_cleanup_interval_seconds=(
                    runtime_settings.background_upload_cleanup_interval_seconds
                ),
                background_session_cleanup_interval_seconds=(
                    runtime_settings.background_session_cleanup_interval_seconds
                ),
                background_digest_interval_seconds=(
                    runtime_settings.background_digest_interval_seconds
                ),
                background_frontier_news_interval_seconds=(
                    runtime_settings.background_frontier_news_interval_seconds
                ),
            )
        for _ in range(runtime_settings.background_job_batch_size):
            job = await service.run_next(
                JOB_HANDLERS,
                worker_id=worker_id or _default_worker_id(),
                queues=queues,
                retry_delay_seconds=runtime_settings.background_job_retry_delay_seconds,
            )
            if job is None:
                break
            processed_count += 1
    return processed_count


async def run_forever() -> None:
    configure_logging()
    settings = get_settings()
    logger = get_logger("worker.background_jobs")
    worker_id = _default_worker_id()
    logger.info(
        "worker_started",
        worker_id=worker_id,
        poll_seconds=settings.background_job_poll_seconds,
        batch_size=settings.background_job_batch_size,
    )

    while True:
        try:
            processed_count = await run_once(settings=settings, worker_id=worker_id)
            logger.info("background_jobs_processed", processed_count=processed_count)
        except Exception as exc:
            logger.exception("background_worker_iteration_failed", error=str(exc))
        await asyncio.sleep(settings.background_job_poll_seconds)


def _payload_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AppError("invalid_job_payload", f"Missing job payload field: {key}", status_code=422)
    return value


def _payload_optional_str(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _payload_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return {str(item_key): item_value for item_key, item_value in value.items()}
    return {}


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:background-jobs"


if __name__ == "__main__":
    asyncio.run(run_forever())
