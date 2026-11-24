from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.db.base import SHANGHAI_TZ, as_utc_datetime
from app.services.background_jobs import BackgroundJobService

CONTENT_QUEUE = "community_content"
CONTENT_TASK = "community_content_slot"
# 海外合集加入现有独立队列；生活小问继续停用，其余栏目及历史帖子保持原样。
CONTENT_CHANNELS = ("weibo_snapshot", "news", "sports", "hot_search", "reading", "overseas")
CONTENT_TIMES = ("10:00", "14:00", "18:00")
SLOT_GRACE = timedelta(minutes=30)


def due_content_slots(now: datetime, start_at: datetime) -> list[datetime]:
    """返回激活水位后、当天已到点且未超过30分钟的北京时间时段。

    参数须带时区；不回填前日或启用前的任务，短暂重连只恢复当前时段。
    """

    if any(value.tzinfo is None or value.utcoffset() is None for value in (now, start_at)):
        raise ValueError("Content scheduling timestamps must be timezone-aware")
    local_now = now.astimezone(SHANGHAI_TZ)
    result = []
    for configured in CONTENT_TIMES:
        scheduled = datetime.combine(local_now.date(), time.fromisoformat(configured), SHANGHAI_TZ)
        if start_at <= scheduled <= local_now < scheduled + SLOT_GRACE:
            result.append(scheduled)
    return result


def content_payload(channel: str, scheduled: datetime) -> dict[str, object]:
    """生成单栏目单时段载荷；固定日期与时段一同入队，重试不改发帖归属。"""

    local = scheduled.astimezone(SHANGHAI_TZ)
    if channel not in CONTENT_CHANNELS or local.strftime("%H:%M") not in CONTENT_TIMES:
        raise ValueError("Unsupported content channel or publication time")
    if local.second or local.microsecond:
        raise ValueError("Content publication time must align to the scheduled minute")
    return {
        "channel": channel,
        "planned_date": local.date().isoformat(),
        "scheduled_time": local.strftime("%H:%M"),
        "scheduled_for": local.isoformat(),
    }


def parse_content_payload(payload: dict[str, object]) -> tuple[str, datetime]:
    """严格核对队列时间的三种表示；拒绝伪造、缺失或互相矛盾的日期。"""

    channel, raw = payload.get("channel"), payload.get("scheduled_for")
    if not isinstance(channel, str) or not isinstance(raw, str):
        raise ValueError("Content job requires channel and scheduled_for")
    scheduled = datetime.fromisoformat(raw)
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        raise ValueError("Content scheduled_for must be timezone-aware")
    expected = content_payload(channel, scheduled)
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("Content job date or time does not match scheduled_for")
    return channel, scheduled


async def enqueue_content_slots(
    service: BackgroundJobService, *, now: datetime, start_at: datetime
) -> int:
    """沿用现有队列唯一幂等键，为六项内容任务分别安排当前新时段；不触及旧队列。"""

    count = 0
    for scheduled in due_content_slots(now, start_at):
        for channel in CONTENT_CHANNELS:
            await service.enqueue(
                CONTENT_TASK,
                queue=CONTENT_QUEUE,
                payload=content_payload(channel, scheduled),
                idempotency_key=f"community:v1:{scheduled.date()}:{scheduled.hour}:{channel}",
                run_at=scheduled.astimezone(UTC),
                max_attempts=3,
                commit=False,
            )
            count += 1
    if count:
        await service.session.commit()
    return count


def content_slot_is_current(scheduled: datetime, now: datetime, start_at: datetime) -> bool:
    """消费/重试前再验当前窗口；过期队列只记跳过，不迟到补发。"""

    current = as_utc_datetime(now)
    return start_at <= scheduled <= current < scheduled + SLOT_GRACE
