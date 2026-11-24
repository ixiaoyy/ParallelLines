from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import insert, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import as_shanghai_datetime, as_utc_datetime
from app.models.traffic import TrafficDailyVisitor, TrafficEvent, TrafficVisitor
from app.services.traffic_queue import QueuedTrafficEvent


async def ingest_traffic_batch(session: AsyncSession, events: list[QueuedTrafficEvent]) -> int:
    """在调用方短事务内批量入库并更新汇总，返回新事件数；不提交、不等待外部网络。

    队列重放先按事件 UUID 排除已提交记录；并发唯一键冲突交由事务整体回滚，
    不能忽略冲突后继续累加日汇总。临时身份只参与浏览量，不进入可靠回访统计。
    """

    if not events:
        return 0
    by_id = {event.event_id: event for event in reversed(events)}
    existing = set(
        await session.scalars(select(TrafficEvent.event_id).where(TrafficEvent.event_id.in_(by_id)))
    )
    fresh = [event for event_id, event in by_id.items() if event_id not in existing]
    if not fresh:
        return 0

    # 每批只做三次批量读取，避免按事件/访客逐条查询和反复提交。
    visitor_events: dict[tuple[str, str], list[QueuedTrafficEvent]] = defaultdict(list)
    daily_events: dict[tuple[date, str, str], list[QueuedTrafficEvent]] = defaultdict(list)
    for event in fresh:
        day = as_shanghai_datetime(event.occurred_at).date()
        for site in (event.site_key, "all"):
            daily_events[(day, site, event.visitor_key)].append(event)
            if event.event_name == "page_view":
                visitor_events[(site, event.visitor_key)].append(event)
    visitors = {}
    if visitor_events:
        visitors = {
            (row.site_key, row.visitor_key): row
            for row in await session.scalars(
                select(TrafficVisitor).where(
                    tuple_(TrafficVisitor.site_key, TrafficVisitor.visitor_key).in_(visitor_events)
                )
            )
        }
    daily = {
        (row.day, row.site_key, row.visitor_key): row
        for row in await session.scalars(
            select(TrafficDailyVisitor).where(
                tuple_(
                    TrafficDailyVisitor.day,
                    TrafficDailyVisitor.site_key,
                    TrafficDailyVisitor.visitor_key,
                ).in_(daily_events)
            )
        )
    }
    await session.execute(insert(TrafficEvent), [event.model_dump() for event in fresh])
    for (site, visitor_key), group in visitor_events.items():
        first, last = _event_bounds(group)
        visitor = visitors.get((site, visitor_key))
        if visitor is None:
            session.add(
                TrafficVisitor(
                    site_key=site,
                    visitor_key=visitor_key,
                    identity_scope=group[0].identity_scope,
                    first_seen_at=first,
                    last_seen_at=last,
                )
            )
        else:
            visitor.first_seen_at = min(as_utc_datetime(visitor.first_seen_at), first)
            visitor.last_seen_at = max(as_utc_datetime(visitor.last_seen_at), last)
    for (day, site, visitor_key), group in daily_events.items():
        first, last = _event_bounds(group)
        row = daily.get((day, site, visitor_key))
        if row is None:
            row = TrafficDailyVisitor(
                day=day,
                site_key=site,
                visitor_key=visitor_key,
                identity_scope=group[0].identity_scope,
                page_views=0,
                actions=0,
                shared_page_views=0,
                first_seen_at=first,
                last_seen_at=last,
            )
            session.add(row)
        row.first_seen_at = min(as_utc_datetime(row.first_seen_at), first)
        row.last_seen_at = max(as_utc_datetime(row.last_seen_at), last)
        views = sum(event.event_name == "page_view" for event in group)
        row.page_views += views
        row.actions += len(group) - views
        if group[0].identity_scope == "shared":
            row.shared_page_views += views
    await session.flush()
    return len(fresh)


def _event_bounds(events: list[QueuedTrafficEvent]) -> tuple[datetime, datetime]:
    """取得一组事件的 UTC 首末时刻；仅用于批内归并，无外部副作用。"""

    times = [as_utc_datetime(event.occurred_at) for event in events]
    return min(times), max(times)
