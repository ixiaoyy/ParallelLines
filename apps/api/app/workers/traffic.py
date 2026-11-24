from __future__ import annotations

import asyncio
import socket
from secrets import token_hex
from time import monotonic

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import utcnow
from app.services.traffic_ingest import ingest_traffic_batch
from app.services.traffic_queue import TRAFFIC_META, TrafficQueue

WORKER_LEASE = "parallellines:traffic:v1:writer-lease"
RELEASE_LEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""


async def run_once(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    queue: TrafficQueue | None = None,
    worker_id: str | None = None,
) -> int:
    """消费一个有20秒总时限的小批次；提交后才确认，崩溃/失败由未确认流在60秒后恢复。"""

    if not settings.traffic_enabled:
        return 0
    queue = queue or TrafficQueue(settings)
    owner = token_hex(16)
    acquired = await queue.client.set(WORKER_LEASE, owner, nx=True, ex=30)
    if not acquired:
        return 0
    try:
        async with asyncio.timeout(20):
            await queue.client.hset(TRAFFIC_META, "worker_last_seen_at", utcnow().isoformat())
            messages = await queue.claim(worker_id or f"{socket.gethostname()}:traffic")
            if not messages:
                return 0
            async with session_factory() as session:
                async with session.begin():
                    inserted = await ingest_traffic_batch(session, [event for _, event in messages])
            # 元数据写入和消息确认都在数据库提交之后，失败时保留消息供幂等重放。
            await queue.client.hset(TRAFFIC_META, "last_ingested_at", utcnow().isoformat())
            await queue.acknowledge([message_id for message_id, _ in messages])
            return inserted
    finally:
        await _release_lease(queue, owner)


async def _release_lease(queue: TrafficQueue, owner: str) -> None:
    """仅释放本批次租约；连接失败由30秒租约到期恢复，不覆盖原始入库异常。"""

    try:
        await queue.client.eval(RELEASE_LEASE_SCRIPT, 1, WORKER_LEASE, owner)
    except (RedisError, OSError):
        return


async def run_forever() -> None:
    """独立低频统计 worker，不占用既有邮件/维护队列；只在显式开关开启时消费。"""

    from app.db.session import AsyncSessionLocal

    configure_logging()
    settings = get_settings()
    logger = get_logger("worker.traffic")
    logger.info(
        "traffic_worker_started",
        enabled=settings.traffic_enabled,
        interval_seconds=settings.traffic_worker_interval_seconds,
        batch_size=settings.traffic_batch_size,
    )
    last_error_log = float("-inf")
    while True:
        try:
            inserted = await run_once(settings=settings, session_factory=AsyncSessionLocal)
            if inserted:
                logger.info("traffic_batch_committed", inserted=inserted)
        except Exception as exc:
            if monotonic() - last_error_log >= 60:
                logger.error("traffic_batch_failed", error_type=type(exc).__name__)
                last_error_log = monotonic()
        await asyncio.sleep(settings.traffic_worker_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
