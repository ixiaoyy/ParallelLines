from __future__ import annotations

import argparse
import asyncio
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.community_content import CommunityContentSettings
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import utcnow
from app.db.session import AsyncSessionLocal, engine
from app.models.background_job import BackgroundJob
from app.services.background_jobs import BackgroundJobService
from app.services.community_schedule import (
    CONTENT_QUEUE,
    CONTENT_TASK,
    content_slot_is_current,
    enqueue_content_slots,
    parse_content_payload,
)

HEARTBEAT = Path("/tmp/parallellines-community-content-heartbeat")
WORKER_LOCK = "parallellines:community-content:v1"


async def handle_content_slot(
    session: AsyncSession, payload: dict[str, object]
) -> dict[str, object]:
    """按已授权栏目执行新时段；无旧任务回接，也不调用互动种子脚本。"""

    activation = CommunityContentSettings()
    if not activation.enabled or activation.start_at is None:
        return {"status": "skipped", "reason": "content_disabled"}
    channel, scheduled = parse_content_payload(payload)
    if not content_slot_is_current(scheduled, utcnow(), activation.start_at):
        return {"status": "skipped", "reason": "outside_current_slot", "channel": channel}

    settings = get_settings()
    if channel == "living":
        from app.services.living_forum import LivingForumService

        return await LivingForumService(session, settings).publish_day(
            scheduled.date(), scheduled_time=scheduled.strftime("%H:%M"), dry_run=False
        )
    if channel == "reading":
        from app.services.daily_reading import DailyReadingService

        return await DailyReadingService(session, settings).publish_day(
            scheduled.date(), scheduled_time=scheduled.strftime("%H:%M"), dry_run=False
        )

    from app.services.scheduled_content import ScheduledContentService

    service = ScheduledContentService(session, settings)
    if channel == "weibo_snapshot":
        return await service.collect_hot_search(scheduled, persist=True)
    return await service.publish_slot(channel, scheduled, dry_run=False)


async def recover_interrupted_jobs(session: AsyncSession) -> int:
    """单实例启动时恢复自身未完成任务；发帖服务以来源/时段去重防止重复写入。

    仅处理独立队列的固定任务名，不触及邮箱、原worker或退休任务；部署必须单实例。
    """

    jobs = list(await session.scalars(select(BackgroundJob).where(
        BackgroundJob.queue == CONTENT_QUEUE,
        BackgroundJob.task_name == CONTENT_TASK,
        BackgroundJob.status == "running",
    ).limit(101)))
    if len(jobs) > 100:
        raise RuntimeError("Too many interrupted content jobs; inspect the owned queue first")
    for job in jobs:
        # 进程崩溃也计入原有三次尝试上限，不以反复重启无限重试。
        job.status = "queued" if job.attempts < job.max_attempts else "dead"
        if job.status == "dead":
            job.finished_at = utcnow()
        job.locked_at = None
        job.locked_by = None
        job.run_at = utcnow().replace(microsecond=0)
        job.last_error = "content_worker_restarted_before_completion"
    await session.commit()
    return len(jobs)


async def run_once() -> int:
    """只调度及消费独立内容队列，每轮最多六项，失败复用既有三次有界重试。"""

    activation = CommunityContentSettings()
    if not activation.enabled or activation.start_at is None:
        return 0
    processed = 0
    async with AsyncSessionLocal() as session:
        service = BackgroundJobService(session)
        await enqueue_content_slots(service, now=utcnow(), start_at=activation.start_at)
        for _ in range(6):
            job = await service.run_next(
                {CONTENT_TASK: handle_content_slot},
                worker_id=f"community:{socket.gethostname()}",
                queues=(CONTENT_QUEUE,),
                retry_delay_seconds=60,
            )
            if job is None:
                break
            processed += 1
            get_logger("worker.community_content").info(
                "content_job_finished", job_id=job.id, status=job.status,
                channel=(job.payload or {}).get("channel"), result=job.result,
                attempts=job.attempts, error=job.last_error,
            )
    return processed


def worker_is_healthy() -> bool:
    """只读健康入口：最近五分钟确实完成过一轮数据库轮询才视为健康。"""

    try:
        seen = datetime.fromisoformat(HEARTBEAT.read_text(encoding="ascii"))
        return 0 <= (utcnow() - seen).total_seconds() < 300
    except (OSError, ValueError, TypeError):
        return False


async def run_forever(*, once: bool = False) -> None:
    """常驻单实例入口；只在显式启用后运行，启动失败非零退出供容器重启/告警。"""

    configure_logging()
    activation = CommunityContentSettings()
    logger = get_logger("worker.community_content")
    if not activation.enabled:
        raise RuntimeError("COMMUNITY_CONTENT_ENABLED must be true for this worker")
    async with single_worker() as connection:
        await run_owned_loop(connection, activation, logger, once=once)


@asynccontextmanager
async def single_worker():
    """以专用 MySQL 连接持有命名锁；无行锁/长事务，第二个实例立即失败。

    独立于业务事务的连接覆盖恢复与消费整个生命周期，手工 --once 也不能并行抢任务。
    """

    async with engine.connect() as raw:
        connection = await raw.execution_options(isolation_level="AUTOCOMMIT")
        acquired = await connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": WORKER_LOCK})
        if acquired != 1:
            raise RuntimeError("Another community content worker already owns this database")
        try:
            yield connection
        finally:
            await connection.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": WORKER_LOCK})


async def run_owned_loop(connection, activation, logger, *, once: bool) -> None:
    """持有单实例锁后才恢复和消费；锁连接丢失即退出，不在失去所有权后继续发帖。"""

    async with AsyncSessionLocal() as session:
        recovered = await recover_interrupted_jobs(session)
    logger.info("content_worker_started", start_at=str(activation.start_at), recovered=recovered)
    while True:
        owned = await connection.scalar(
            text("SELECT IS_USED_LOCK(:name) = CONNECTION_ID()"), {"name": WORKER_LOCK}
        )
        if owned != 1:
            raise RuntimeError("Community worker lost its single-instance lock")
        try:
            await run_once()
            HEARTBEAT.write_text(utcnow().isoformat(), encoding="ascii")
        except Exception as exc:
            logger.exception("content_worker_iteration_failed", error=str(exc))
            if once:
                raise
        if once:
            return
        await asyncio.sleep(15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="独立三时段圈子自动内容 worker")
    parser.add_argument("--once", action="store_true", help="仅执行一次当前时段轮询，不补发")
    parser.add_argument("--health", action="store_true", help="只读检查内容轮询心跳，不运行任务")
    args = parser.parse_args()
    if args.health:
        raise SystemExit(0 if worker_is_healthy() else 1)
    asyncio.run(run_forever(once=args.once))
