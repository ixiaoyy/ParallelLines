from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AnalyticsMetricPoint(BaseModel):
    day: date
    dau: int = 0
    registrations: int = 0
    topics: int = 0
    posts: int = 0
    likes: int = 0
    flags: int = 0


class AnalyticsTotalsResponse(BaseModel):
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


class AnalyticsOverviewResponse(BaseModel):
    start_date: date
    end_date: date
    totals: AnalyticsTotalsResponse
    series: list[AnalyticsMetricPoint]
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
