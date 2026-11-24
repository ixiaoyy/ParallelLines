from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256

from pydantic import ValidationError as PayloadValidationError
from redis.exceptions import RedisError
from sqlalchemy import and_, case, distinct, exists, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.core.response_cache import ResponseHotCache
from app.db.base import SHANGHAI_TZ, as_shanghai_datetime, as_utc_datetime, utcnow
from app.models.traffic import TrafficDailyVisitor, TrafficEvent, TrafficVisitor
from app.models.user import User
from app.schemas.traffic import (
    TrafficAction,
    TrafficMetrics,
    TrafficOverviewResponse,
    TrafficPage,
    TrafficPoint,
    TrafficRetention,
    TrafficSelection,
    TrafficSite,
    TrafficSource,
)
from app.services.traffic_queue import SITE_NAMES, TRAFFIC_META, TRAFFIC_REPORT_PREFIX, TrafficQueue

REPORT_CACHE_SECONDS = 300
_REPORT_CACHE = ResponseHotCache[str](ttl_seconds=REPORT_CACHE_SECONDS, max_entries=32)
_REPORT_LOCK = asyncio.Lock()


class TrafficService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        queue: TrafficQueue | None = None,
        now: datetime | None = None,
    ) -> None:
        """绑定只读统计会话、配置和可注入队列；now 仅用于一致的报表时间窗口。"""

        self.session = session
        self.settings = settings
        self.queue = queue or TrafficQueue(settings)
        self.now = as_utc_datetime(now or utcnow())

    async def overview(
        self,
        current_user: User,
        *,
        start_date: date | None,
        end_date: date | None,
        site_key: TrafficSelection,
    ) -> TrafficOverviewResponse:
        """读取管理员流量总览；缓存300秒、不支持强制绕过，队列状态每次独立更新。"""

        if not is_admin(current_user):
            raise PermissionDeniedError()
        start, end = self._range(start_date, end_date)
        if not self.settings.traffic_enabled:
            return TrafficOverviewResponse(
                enabled=False,
                status="disabled",
                start_date=start,
                end_date=end,
                site_key=site_key,
                generated_at=self.now,
                queue=await self.queue.status(),
                sites=[
                    TrafficSite(site_key=key, name=name, status="disabled")
                    for key, name in SITE_NAMES.items()
                ],
            )
        scope = sha256(self.settings.database_url.encode()).hexdigest()[:16]
        cache_key = f"{TRAFFIC_REPORT_PREFIX}{scope}:{site_key}:{start}:{end}"
        cached = _REPORT_CACHE.get(cache_key)
        if cached is None:
            cached = await self._read_shared_cache(cache_key)
        if cached is None:
            try:
                # 限制同一进程报表并发和总时间；统计查询不在普通页面/业务请求中执行。
                async with asyncio.timeout(8), _REPORT_LOCK:
                    cached = _REPORT_CACHE.get(cache_key)
                    if cached is None:
                        report = await self._build(start, end, site_key)
                        cached = report.model_dump_json()
                        await self._write_cache(cache_key, cached)
            except (SQLAlchemyError, TimeoutError) as exc:
                raise AppError(
                    "traffic_report_unavailable",
                    "流量报表暂不可用，请检查迁移和统计 worker",
                    status_code=503,
                ) from exc
        report = TrafficOverviewResponse.model_validate_json(cached)
        # 命中报表缓存也不复用旧的健康状态，避免 Redis 断开或满载仍显示正常。
        report.queue = await self.queue.status()
        if report.queue.status not in {"disabled", "unavailable"}:
            last_ingested = await self._last_ingested()
            if last_ingested is not None:
                report.last_ingested_at = last_ingested
        return report

    async def _build(
        self, start: date, end: date, site: TrafficSelection
    ) -> TrafficOverviewResponse:
        """基于已提交日汇总生成固定快照；页面/来源排行只在缓存未命中时读取原始统计表。"""

        first_seen = await self.session.scalar(
            select(func.min(TrafficVisitor.first_seen_at)).where(TrafficVisitor.site_key == site)
        )
        latest_query = select(func.max(TrafficEvent.received_at))
        if site != "all":
            latest_query = latest_query.where(TrafficEvent.site_key == site)
        latest_received = await self.session.scalar(latest_query)
        last_by_site = dict(
            (
                await self.session.execute(
                    select(TrafficEvent.site_key, func.max(TrafficEvent.received_at))
                    .where(TrafficEvent.event_name == "page_view")
                    .group_by(TrafficEvent.site_key)
                )
            ).all()
        )
        sites = await self._sites(start, end, last_by_site)
        report = TrafficOverviewResponse(
            enabled=True,
            status="ready" if first_seen is not None else "not_connected",
            start_date=start,
            end_date=end,
            site_key=site,
            generated_at=self.now,
            data_through=as_utc_datetime(latest_received) if latest_received else None,
            collection_started_at=as_utc_datetime(first_seen) if first_seen else None,
            queue=await self.queue.status(),
            sites=sites,
        )
        if first_seen is None:
            return report
        days = (end - start).days + 1
        report.totals = await self._metrics(start, end, site)
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        # 上期早于本站采集记录时保持未知，不能把未采集历史当零来制造增长。
        if as_shanghai_datetime(first_seen).date() <= previous_start:
            report.previous = await self._metrics(previous_start, previous_end, site)
        report.series = await self._series(start, end, site)
        report.traffic_sources = await self._sources(start, end, site)
        report.top_pages = await self._pages(start, end, site)
        report.top_actions = await self._actions(start, end, site)
        report.retention = await self._retention(start, end, site)
        return report

    async def _metrics(self, start: date, end: date, site: str) -> TrafficMetrics:
        """按日汇总和首次访问表计算 PV/浏览器 UV、新回访；临时标识不进入新回访分母。"""

        day = TrafficDailyVisitor
        visitor = TrafficVisitor
        has_view = day.page_views > 0
        stable = day.identity_scope != "ephemeral"
        start_dt, _ = self._bounds(start, end)
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(day.page_views), 0),
                    func.count(distinct(case((has_view, day.visitor_key)))),
                    *(
                        func.count(
                            distinct(
                                case((and_(has_view, day.identity_scope == scope), day.visitor_key))
                            )
                        )
                        for scope in ("shared", "site", "ephemeral")
                    ),
                    func.count(
                        distinct(
                            case(
                                (
                                    and_(has_view, stable, visitor.first_seen_at >= start_dt),
                                    day.visitor_key,
                                )
                            )
                        )
                    ),
                    func.count(
                        distinct(
                            case(
                                (
                                    and_(has_view, stable, visitor.first_seen_at < start_dt),
                                    day.visitor_key,
                                )
                            )
                        )
                    ),
                    func.coalesce(func.sum(day.actions), 0),
                )
                .select_from(day)
                .outerjoin(
                    visitor,
                    and_(visitor.site_key == day.site_key, visitor.visitor_key == day.visitor_key),
                )
                .where(day.site_key == site, day.day >= start, day.day <= end)
            )
        ).one()
        return TrafficMetrics(
            page_views=int(row[0]),
            unique_visitors=int(row[1]),
            shared_unique_visitors=int(row[2]),
            site_only_visitors=int(row[3]),
            ephemeral_visitors=int(row[4]),
            new_visitors=int(row[5]),
            returning_visitors=int(row[6]),
            actions=int(row[7]),
        )

    async def _series(self, start: date, end: date, site: str) -> list[TrafficPoint]:
        """返回上海日界的连续日序列；仅已接入站点将无访问日补零。"""

        day = TrafficDailyVisitor
        rows = (
            await self.session.execute(
                select(
                    day.day,
                    func.sum(day.page_views),
                    func.count(distinct(case((day.page_views > 0, day.visitor_key)))),
                    func.count(
                        distinct(
                            case(
                                (
                                    and_(day.page_views > 0, day.identity_scope == "shared"),
                                    day.visitor_key,
                                )
                            )
                        )
                    ),
                )
                .where(day.site_key == site, day.day >= start, day.day <= end)
                .group_by(day.day)
            )
        ).all()
        by_day = {row[0]: row for row in rows}
        return [
            TrafficPoint(
                day=current,
                page_views=int(by_day[current][1]) if current in by_day else 0,
                unique_visitors=int(by_day[current][2]) if current in by_day else 0,
                shared_unique_visitors=int(by_day[current][3]) if current in by_day else 0,
            )
            for current in (
                start + timedelta(days=index) for index in range((end - start).days + 1)
            )
        ]

    async def _sites(self, start: date, end: date, last_by_site: dict) -> list[TrafficSite]:
        """批量读取分站统计；从未采集的站点指标为 null，长时间无事件只提示最近性未知。"""

        day = TrafficDailyVisitor
        rows = (
            await self.session.execute(
                select(
                    day.site_key,
                    func.sum(day.page_views),
                    func.count(distinct(case((day.page_views > 0, day.visitor_key)))),
                    func.sum(day.actions),
                )
                .where(day.site_key != "all", day.day >= start, day.day <= end)
                .group_by(day.site_key)
            )
        ).all()
        counts = {row[0]: row[1:] for row in rows}
        sites = []
        for key, name in SITE_NAMES.items():
            received = last_by_site.get(key)
            if received is None:
                sites.append(TrafficSite(site_key=key, name=name, status="not_connected"))
                continue
            received = as_utc_datetime(received)
            views, visitors, actions = counts.get(key, (0, 0, 0))
            status = "collecting" if views else "no_activity"
            if received < self.now - timedelta(hours=24):
                status = "stale"
            sites.append(
                TrafficSite(
                    site_key=key,
                    name=name,
                    status=status,
                    last_received_at=received,
                    page_views=int(views),
                    unique_visitors=int(visitors),
                    actions=int(actions),
                )
            )
        return sites

    async def _sources(self, start: date, end: date, site: str) -> list[TrafficSource]:
        """从已提交页面事件读取最多20条来源聚合；不包含来源路径和查询参数。"""

        event = TrafficEvent
        count = func.count(event.event_id)
        rows = (
            await self.session.execute(
                select(
                    event.source_type,
                    event.source_name,
                    count,
                    func.count(distinct(event.visitor_key)),
                )
                .where(*self._event_conditions(start, end, site), event.event_name == "page_view")
                .group_by(event.source_type, event.source_name)
                .order_by(count.desc(), event.source_type, event.source_name)
                .limit(20)
            )
        ).all()
        return [
            TrafficSource(
                source_type=row[0], source_name=row[1], page_views=row[2], unique_visitors=row[3]
            )
            for row in rows
        ]

    async def _pages(self, start: date, end: date, site: str) -> list[TrafficPage]:
        """读取最多20个热门页面，保留站点维度，避免不同子站的根路径相互混淆。"""

        event = TrafficEvent
        count = func.count(event.event_id)
        rows = (
            await self.session.execute(
                select(event.site_key, event.path, count, func.count(distinct(event.visitor_key)))
                .where(*self._event_conditions(start, end, site), event.event_name == "page_view")
                .group_by(event.site_key, event.path)
                .order_by(count.desc(), event.site_key, event.path)
                .limit(20)
            )
        ).all()
        return [
            TrafficPage(site_key=row[0], path=row[1], page_views=row[2], unique_visitors=row[3])
            for row in rows
        ]

    async def _actions(self, start: date, end: date, site: str) -> list[TrafficAction]:
        """读取实际接入的游戏打开或工具结果按钮点击排行，不将页面打开冒充成功使用。"""

        event = TrafficEvent
        count = func.count(event.event_id)
        rows = (
            await self.session.execute(
                select(
                    event.site_key,
                    event.event_name,
                    event.path,
                    count,
                    func.count(distinct(event.visitor_key)),
                )
                .where(*self._event_conditions(start, end, site), event.event_name != "page_view")
                .group_by(event.site_key, event.event_name, event.path)
                .order_by(count.desc(), event.site_key, event.event_name, event.path)
                .limit(20)
            )
        ).all()
        return [
            TrafficAction(
                site_key=row[0],
                event_name=row[1],
                path=row[2],
                count=row[3],
                unique_visitors=row[4],
            )
            for row in rows
        ]

    async def _retention(self, start: date, end: date, site: str) -> TrafficRetention:
        """计算完整成熟7天队列的回访率；只算首次日后1—7日有页面访问的稳定标识。"""

        last_complete_day = min(end, as_shanghai_datetime(self.now).date() - timedelta(days=1))
        cohort_end = last_complete_day - timedelta(days=7)
        if cohort_end < start:
            return TrafficRetention()
        visitor = TrafficVisitor
        day = TrafficDailyVisitor
        dialect = self.session.get_bind().dialect.name
        if dialect == "sqlite":
            first_day = func.date(visitor.first_seen_at, "+8 hours")
            seventh_day = func.date(visitor.first_seen_at, "+8 hours", "+7 days")
        else:
            first_day = func.date(func.convert_tz(visitor.first_seen_at, "+00:00", "+08:00"))
            seventh_day = func.date_add(first_day, text("INTERVAL 7 DAY"))
        returned = exists(
            select(1).where(
                day.site_key == site,
                day.visitor_key == visitor.visitor_key,
                day.page_views > 0,
                day.day > first_day,
                day.day <= seventh_day,
            )
        )
        first, after = self._bounds(start, cohort_end)
        eligible, count = (
            await self.session.execute(
                select(func.count(), func.coalesce(func.sum(case((returned, 1), else_=0)), 0))
                .select_from(visitor)
                .where(
                    visitor.site_key == site,
                    visitor.identity_scope != "ephemeral",
                    visitor.first_seen_at >= first,
                    visitor.first_seen_at < after,
                )
            )
        ).one()
        return TrafficRetention(
            eligible_visitors=int(eligible),
            returned_visitors=int(count),
            rate=round(int(count) / int(eligible) * 100, 1) if eligible else None,
            cohort_start=start,
            cohort_end=cohort_end,
        )

    def _event_conditions(self, start: date, end: date, site: str) -> list:
        """构造事件索引范围；全局仅去掉站点过滤，不对业务数据做跨表查询。"""

        first, after = self._bounds(start, end)
        conditions = [TrafficEvent.occurred_at >= first, TrafficEvent.occurred_at < after]
        if site != "all":
            conditions.append(TrafficEvent.site_key == site)
        return conditions

    def _range(self, start: date | None, end: date | None) -> tuple[date, date]:
        """限制查询到最多366个上海自然日，默认最近30天，不允许未来结束日期。"""

        today = as_shanghai_datetime(self.now).date()
        end = end or today
        start = start or end - timedelta(days=29)
        if start > end or (end - start).days >= 366 or end > today:
            raise ValidationError("traffic_range_invalid", "统计日期需为最多366天且不晚于今天")
        return start, end

    @staticmethod
    def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
        """将上海自然日转换为左闭右开的UTC范围，避免相邻日期重复计入边界。"""

        return (
            datetime.combine(start, time.min, SHANGHAI_TZ).astimezone(UTC),
            datetime.combine(end + timedelta(days=1), time.min, SHANGHAI_TZ).astimezone(UTC),
        )

    async def _read_shared_cache(self, key: str) -> str | None:
        """读取统计专用缓存；连接不可用或旧版本缓存不兼容时才重新读取统计表。"""

        try:
            cached = await self.queue.client.get(key)
            if cached is not None:
                TrafficOverviewResponse.model_validate_json(cached)
                # 共享缓存命中不重新起算本地TTL，避免将快到期快照再延长五分钟。
            return cached
        except (RedisError, OSError, PayloadValidationError):
            return None

    async def _write_cache(self, key: str, content: str) -> None:
        """保存有上限的本进程缓存和300秒Redis缓存；Redis异常不丢失已生成的只读结果。"""

        _REPORT_CACHE.set(key, content)
        try:
            await self.queue.client.set(key, content, ex=REPORT_CACHE_SECONDS)
        except (RedisError, OSError):
            return

    async def _last_ingested(self) -> datetime | None:
        """读取仅在SQL提交后写入的worker提交时间；不可用时不编造入库时间。"""

        try:
            value = await self.queue.client.hget(TRAFFIC_META, "last_ingested_at")
        except (RedisError, OSError):
            return None
        return as_utc_datetime(datetime.fromisoformat(value)) if value else None
