from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AnalyticsMetricPoint(BaseModel):
    day: date
    page_views: int = 0
    unique_visitors: int = 0
    dau: int = 0
    registrations: int = 0
    topics: int = 0
    posts: int = 0
    likes: int = 0
    flags: int = 0


class AnalyticsTotalsResponse(BaseModel):
    page_views: int
    unique_visitors: int
    authenticated_member_visitors: int = Field(
        description=(
            "已登录、非管理员且未标记为运营/测试账号的独立访客数；"
            "这是后台最可信的真人访问信号。"
        )
    )
    anonymous_visitors: int = Field(
        description="未登录浏览器的独立访客数；可能包含无法识别的自动化访问。"
    )
    operator_visitors: int = Field(
        description="管理员或已标记为运营/测试账号的独立访客数。"
    )
    external_referrals: int
    dau: int
    mau: int
    registrations: int
    topics: int
    posts: int
    likes: int
    flags: int


class AnalyticsTopBoardResponse(BaseModel):
    id: str
    slug: str
    name: str
    topic_count: int
    post_count: int


class AnalyticsTopTopicResponse(BaseModel):
    id: str
    slug: str
    title: str
    board_slug: str
    reply_count: int
    like_count: int
    view_count: int


class AnalyticsTopUserResponse(BaseModel):
    id: str
    username: str
    post_count: int
    topic_count: int
    points_balance: int


class AnalyticsTrafficSourceResponse(BaseModel):
    source_type: str
    source_name: str
    visit_count: int
    unique_visitors: int


class AnalyticsEntryPageResponse(BaseModel):
    path: str
    title: str | None = None
    visit_count: int
    unique_visitors: int


class AnalyticsOverviewResponse(BaseModel):
    start_date: date
    end_date: date
    totals: AnalyticsTotalsResponse
    series: list[AnalyticsMetricPoint]
    traffic_sources: list[AnalyticsTrafficSourceResponse] = Field(default_factory=list)
    entry_pages: list[AnalyticsEntryPageResponse] = Field(default_factory=list)
    top_boards: list[AnalyticsTopBoardResponse]
    top_topics: list[AnalyticsTopTopicResponse]
    top_users: list[AnalyticsTopUserResponse]


class DataExplorerReportSummary(BaseModel):
    id: str
    name: str
    description: str
    columns: list[str] = Field(default_factory=list)


class DataExplorerReportResponse(DataExplorerReportSummary):
    rows: list[dict[str, object]] = Field(default_factory=list)


class SiteVisitCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=180)
    referrer: str | None = Field(default=None, max_length=1024)


class SiteVisitRecordResponse(BaseModel):
    recorded: bool
