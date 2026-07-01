from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from typing import Any

from sqlalchemy import desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.analytics import SiteVisit
from app.models.forum import Board, Post, Topic
from app.models.interaction import Reaction
from app.models.moderation import AuditLog, Flag
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsEntryPageResponse,
    AnalyticsMetricPoint,
    AnalyticsOverviewResponse,
    AnalyticsTopBoardResponse,
    AnalyticsTopTopicResponse,
    AnalyticsTopUserResponse,
    AnalyticsTotalsResponse,
    AnalyticsTrafficSourceResponse,
    DataExplorerReportResponse,
    DataExplorerReportSummary,
)

MAX_ANALYTICS_DAYS = 366


@dataclass(frozen=True)
class ReportDefinition:
    id: str
    name: str
    description: str
    columns: tuple[str, ...]


REPORTS: dict[str, ReportDefinition] = {
    "daily_activity": ReportDefinition(
        id="daily_activity",
        name="每日活跃趋势",
        description="按天输出 PV、UV、DAU、注册、发帖、回复、点赞和举报。",
        columns=(
            "day",
            "page_views",
            "unique_visitors",
            "dau",
            "registrations",
            "topics",
            "posts",
            "likes",
            "flags",
        ),
    ),
    "traffic_sources": ReportDefinition(
        id="traffic_sources",
        name="访问来源",
        description="按来源类型和来源名称聚合 PV 与 UV。",
        columns=("source_type", "source_name", "visit_count", "unique_visitors"),
    ),
    "entry_pages": ReportDefinition(
        id="entry_pages",
        name="入口页",
        description="按访问落地页聚合 PV 与 UV。",
        columns=("path", "title", "visit_count", "unique_visitors"),
    ),
    "top_topics": ReportDefinition(
        id="top_topics",
        name="热门主题",
        description="按回复、点赞和浏览排序的主题列表。",
        columns=("topic_id", "title", "board_slug", "reply_count", "like_count", "view_count"),
    ),
    "top_users": ReportDefinition(
        id="top_users",
        name="活跃成员",
        description="按发帖贡献排序的成员列表。",
        columns=("user_id", "username", "post_count", "topic_count", "points_balance"),
    ),
    "flags_by_reason": ReportDefinition(
        id="flags_by_reason",
        name="举报原因分布",
        description="按原因和状态聚合举报量。",
        columns=("reason", "status", "count"),
    ),
}


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(
        self,
        current_user: User,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> AnalyticsOverviewResponse:
        self._require_admin(current_user)
        start, end = self._range(start_date, end_date)
        series = await self._series(start, end)
        totals = AnalyticsTotalsResponse(
            page_views=sum(point.page_views for point in series),
            unique_visitors=await self._unique_site_visitors(start, end),
            external_referrals=await self._external_referrals(start, end),
            dau=max((point.dau for point in series), default=0),
            mau=await self._active_users(start, end),
            registrations=sum(point.registrations for point in series),
            topics=sum(point.topics for point in series),
            posts=sum(point.posts for point in series),
            likes=sum(point.likes for point in series),
            flags=sum(point.flags for point in series),
        )
        return AnalyticsOverviewResponse(
            start_date=start,
            end_date=end,
            totals=totals,
            series=series,
            traffic_sources=await self._traffic_sources(start, end),
            entry_pages=await self._entry_pages(start, end),
            top_boards=await self._top_boards(),
            top_topics=await self._top_topics(start, end),
            top_users=await self._top_users(start, end),
        )

    async def report_summaries(self, current_user: User) -> list[DataExplorerReportSummary]:
        self._require_admin(current_user)
        return [
            DataExplorerReportSummary(
                id=definition.id,
                name=definition.name,
                description=definition.description,
                columns=list(definition.columns),
            )
            for definition in REPORTS.values()
        ]

    async def run_report(
        self,
        current_user: User,
        report_id: str,
        *,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> DataExplorerReportResponse:
        self._require_admin(current_user)
        definition = self._report_definition(report_id)
        start, end = self._range(start_date, end_date)
        rows = await self._report_rows(definition.id, start, end, limit)
        return DataExplorerReportResponse(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            columns=list(definition.columns),
            rows=rows,
        )

    async def export_report_csv(
        self,
        current_user: User,
        report_id: str,
        *,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> str:
        report = await self.run_report(
            current_user,
            report_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=report.columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.rows)
        self.session.add(
            AuditLog(
                actor_id=current_user.id,
                action="analytics_csv_exported",
                target_type="analytics_report",
                target_id=report.id,
                data={
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                    "limit": limit,
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()
        return buffer.getvalue()

    async def _series(self, start: date, end: date) -> list[AnalyticsMetricPoint]:
        points = {
            start + timedelta(days=offset): AnalyticsMetricPoint(day=start + timedelta(days=offset))
            for offset in range((end - start).days + 1)
        }
        await self._fill_count(points, User.created_at, "registrations", start, end)
        await self._fill_count(
            points,
            Topic.created_at,
            "topics",
            start,
            end,
            Topic.topic_type == "regular",
        )
        await self._fill_count(points, Post.created_at, "posts", start, end)
        await self._fill_count(points, Reaction.created_at, "likes", start, end)
        await self._fill_count(points, Flag.created_at, "flags", start, end)
        await self._fill_active_users(points, start, end)
        await self._fill_site_visits(points, start, end)
        return list(points.values())

    async def _fill_count(
        self,
        points: dict[date, AnalyticsMetricPoint],
        column,
        field: str,
        start: date,
        end: date,
        *conditions,
    ) -> None:
        rows = await self.session.execute(
            select(func.date(column), func.count())
            .where(column >= self._start_dt(start), column <= self._end_dt(end), *conditions)
            .group_by(func.date(column))
        )
        for day_value, count in rows:
            day = self._coerce_day(day_value)
            if day in points:
                setattr(points[day], field, int(count))

    async def _fill_active_users(
        self,
        points: dict[date, AnalyticsMetricPoint],
        start: date,
        end: date,
    ) -> None:
        rows = await self.session.execute(
            select(func.date(User.last_seen_at), func.count(distinct(User.id)))
            .where(
                User.last_seen_at >= self._start_dt(start), User.last_seen_at <= self._end_dt(end)
            )
            .group_by(func.date(User.last_seen_at))
        )
        for day_value, count in rows:
            day = self._coerce_day(day_value)
            if day in points:
                points[day].dau = int(count)

    async def _fill_site_visits(
        self,
        points: dict[date, AnalyticsMetricPoint],
        start: date,
        end: date,
    ) -> None:
        """Fill daily PV and UV values from immutable site visit events.

        Key parameters are the day-indexed metric points and inclusive date
        range. Return value is none. Side effect: mutates matching points.
        """

        visit_day = func.date(SiteVisit.created_at)
        rows = await self.session.execute(
            select(
                visit_day,
                func.count(SiteVisit.id),
                func.count(distinct(SiteVisit.visitor_key)),
            )
            .where(
                SiteVisit.created_at >= self._start_dt(start),
                SiteVisit.created_at <= self._end_dt(end),
            )
            .group_by(visit_day)
        )
        for day_value, page_views, unique_visitors in rows:
            day = self._coerce_day(day_value)
            if day in points:
                points[day].page_views = int(page_views)
                points[day].unique_visitors = int(unique_visitors)

    async def _active_users(self, start: date, end: date) -> int:
        count = await self.session.scalar(
            select(func.count(distinct(User.id))).where(
                User.last_seen_at >= self._start_dt(start),
                User.last_seen_at <= self._end_dt(end),
            )
        )
        return int(count or 0)

    async def _unique_site_visitors(self, start: date, end: date) -> int:
        """Count unique site visitors across an inclusive date range.

        Key parameters are start and end dates. Return value is UV based on the
        privacy-preserving visitor key. Side effect: none.
        """

        count = await self.session.scalar(
            select(func.count(distinct(SiteVisit.visitor_key))).where(
                SiteVisit.created_at >= self._start_dt(start),
                SiteVisit.created_at <= self._end_dt(end),
            )
        )
        return int(count or 0)

    async def _external_referrals(self, start: date, end: date) -> int:
        """Count acquisition visits from external or campaign sources.

        Key parameters are start and end dates. Return value is PV from UTM,
        search, social, and referral sources. Side effect: none.
        """

        count = await self.session.scalar(
            select(func.count(SiteVisit.id)).where(
                SiteVisit.created_at >= self._start_dt(start),
                SiteVisit.created_at <= self._end_dt(end),
                SiteVisit.source_type.in_(("campaign", "search", "social", "referral")),
            )
        )
        return int(count or 0)

    async def _top_boards(self, limit: int = 8) -> list[AnalyticsTopBoardResponse]:
        boards = list(
            await self.session.scalars(
                select(Board)
                .where(Board.visibility == "public")
                .order_by(desc(Board.topic_count), desc(Board.post_count))
                .limit(limit)
            )
        )
        return [
            AnalyticsTopBoardResponse(
                id=board.id,
                slug=board.slug,
                name=board.name,
                topic_count=board.topic_count,
                post_count=board.post_count,
            )
            for board in boards
        ]

    async def _top_topics(
        self, start: date, end: date, limit: int = 8
    ) -> list[AnalyticsTopTopicResponse]:
        topics = list(
            await self.session.scalars(
                select(Topic)
                .join(Board)
                .options(selectinload(Topic.board))
                .where(
                    Topic.created_at >= self._start_dt(start),
                    Topic.created_at <= self._end_dt(end),
                    Topic.visibility != "private_message",
                )
                .order_by(desc(Topic.reply_count), desc(Topic.like_count), desc(Topic.view_count))
                .limit(limit)
            )
        )
        return [
            AnalyticsTopTopicResponse(
                id=topic.id,
                slug=topic.slug,
                title=topic.title,
                board_slug=topic.board.slug,
                reply_count=topic.reply_count,
                like_count=topic.like_count,
                view_count=topic.view_count,
            )
            for topic in topics
        ]

    async def _top_users(
        self, start: date, end: date, limit: int = 8
    ) -> list[AnalyticsTopUserResponse]:
        post_count = func.count(Post.id).label("post_count")
        post_rows = await self.session.execute(
            select(User, post_count)
            .join(Post, Post.user_id == User.id)
            .where(Post.created_at >= self._start_dt(start), Post.created_at <= self._end_dt(end))
            .group_by(User.id)
            .order_by(desc(post_count))
            .limit(limit)
        )
        users = [(user, int(post_count)) for user, post_count in post_rows]
        topic_counts = await self._topic_counts_for_users(
            [user.id for user, _ in users], start, end
        )
        return [
            AnalyticsTopUserResponse(
                id=user.id,
                username=user.username,
                post_count=post_count,
                topic_count=topic_counts.get(user.id, 0),
                points_balance=user.points_balance,
            )
            for user, post_count in users
        ]

    async def _traffic_sources(
        self,
        start: date,
        end: date,
        limit: int = 8,
    ) -> list[AnalyticsTrafficSourceResponse]:
        """Return top traffic sources for acquisition and direct/internal mix.

        Key parameters are start/end dates and row limit. Return value is a
        visit-count sorted source list. Side effect: none.
        """

        visit_count = func.count(SiteVisit.id)
        unique_visitors = func.count(distinct(SiteVisit.visitor_key))
        rows = await self.session.execute(
            select(
                SiteVisit.source_type,
                SiteVisit.source_name,
                visit_count,
                unique_visitors,
            )
            .where(
                SiteVisit.created_at >= self._start_dt(start),
                SiteVisit.created_at <= self._end_dt(end),
            )
            .group_by(SiteVisit.source_type, SiteVisit.source_name)
            .order_by(desc(visit_count))
            .limit(limit)
        )
        return [
            AnalyticsTrafficSourceResponse(
                source_type=source_type,
                source_name=source_name,
                visit_count=int(row_visit_count),
                unique_visitors=int(row_unique_visitors),
            )
            for source_type, source_name, row_visit_count, row_unique_visitors in rows
        ]

    async def _entry_pages(
        self,
        start: date,
        end: date,
        limit: int = 8,
    ) -> list[AnalyticsEntryPageResponse]:
        """Return the most visited landing pages for the selected range.

        Key parameters are start/end dates and row limit. Return value is a
        visit-count sorted path list. Side effect: none.
        """

        visit_count = func.count(SiteVisit.id)
        unique_visitors = func.count(distinct(SiteVisit.visitor_key))
        rows = await self.session.execute(
            select(
                SiteVisit.path,
                func.max(SiteVisit.title),
                visit_count,
                unique_visitors,
            )
            .where(
                SiteVisit.created_at >= self._start_dt(start),
                SiteVisit.created_at <= self._end_dt(end),
            )
            .group_by(SiteVisit.path)
            .order_by(desc(visit_count))
            .limit(limit)
        )
        return [
            AnalyticsEntryPageResponse(
                path=path,
                title=title,
                visit_count=int(row_visit_count),
                unique_visitors=int(row_unique_visitors),
            )
            for path, title, row_visit_count, row_unique_visitors in rows
        ]

    async def _topic_counts_for_users(
        self,
        user_ids: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, int]:
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(Topic.user_id, func.count(Topic.id))
            .where(
                Topic.user_id.in_(user_ids),
                Topic.created_at >= self._start_dt(start),
                Topic.created_at <= self._end_dt(end),
            )
            .group_by(Topic.user_id)
        )
        return {str(user_id): int(count) for user_id, count in rows}

    async def _report_rows(
        self,
        report_id: str,
        start: date,
        end: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        if report_id == "daily_activity":
            return [point.model_dump(mode="json") for point in await self._series(start, end)]
        if report_id == "traffic_sources":
            return [
                source.model_dump(mode="json")
                for source in await self._traffic_sources(start, end, limit)
            ]
        if report_id == "entry_pages":
            return [
                entry.model_dump(mode="json")
                for entry in await self._entry_pages(start, end, limit)
            ]
        if report_id == "top_topics":
            return [
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "board_slug": topic.board_slug,
                    "reply_count": topic.reply_count,
                    "like_count": topic.like_count,
                    "view_count": topic.view_count,
                }
                for topic in await self._top_topics(start, end, limit)
            ]
        if report_id == "top_users":
            return [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "post_count": user.post_count,
                    "topic_count": user.topic_count,
                    "points_balance": user.points_balance,
                }
                for user in await self._top_users(start, end, limit)
            ]
        if report_id == "flags_by_reason":
            rows = await self.session.execute(
                select(Flag.reason, Flag.status, func.count(Flag.id))
                .where(
                    Flag.created_at >= self._start_dt(start), Flag.created_at <= self._end_dt(end)
                )
                .group_by(Flag.reason, Flag.status)
                .order_by(desc(func.count(Flag.id)))
                .limit(limit)
            )
            return [
                {"reason": reason, "status": status, "count": int(count)}
                for reason, status, count in rows
            ]
        raise NotFoundError("analytics_report_not_found", "Analytics report not found")

    def _report_definition(self, report_id: str) -> ReportDefinition:
        definition = REPORTS.get(report_id)
        if definition is None:
            raise NotFoundError("analytics_report_not_found", "Analytics report not found")
        return definition

    def _range(self, start_date: date | None, end_date: date | None) -> tuple[date, date]:
        today = utcnow().date()
        end = end_date or today
        start = start_date or (end - timedelta(days=29))
        if start > end:
            raise ValidationError("invalid_analytics_range", "Start date must be before end date.")
        if (end - start).days > MAX_ANALYTICS_DAYS:
            raise ValidationError("invalid_analytics_range", "Analytics range is too large.")
        return start, end

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _start_dt(self, value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    def _end_dt(self, value: date) -> datetime:
        return datetime.combine(value, time.max, tzinfo=UTC)

    def _coerce_day(self, value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
