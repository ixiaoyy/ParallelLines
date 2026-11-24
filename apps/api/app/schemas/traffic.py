from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TrafficSiteKey = Literal["games", "forum", "tools", "chat", "api"]
TrafficSelection = Literal["all", "games", "forum", "tools", "chat", "api"]
TrafficIdentityScope = Literal["shared", "site", "ephemeral"]
TrafficEventName = Literal["page_view", "game_open", "tool_download", "tool_copy"]


class TrafficEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    site_key: TrafficSiteKey
    event_name: TrafficEventName
    path: str = Field(min_length=1, max_length=512)
    referrer: str | None = Field(default=None, max_length=1024)
    campaign_source: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    occurred_at: datetime


class TrafficBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visitor_id: str = Field(min_length=8, max_length=128)
    identity_scope: TrafficIdentityScope
    events: list[TrafficEventRequest] = Field(min_length=1, max_length=20)


class TrafficAcceptedResponse(BaseModel):
    accepted: int


class TrafficMetrics(BaseModel):
    # 未采集使用 null；已接入但选定区间没有访问才是 0。
    page_views: int | None = None
    unique_visitors: int | None = None
    shared_unique_visitors: int | None = None
    site_only_visitors: int | None = None
    ephemeral_visitors: int | None = None
    new_visitors: int | None = None
    returning_visitors: int | None = None
    actions: int | None = None


class TrafficPoint(BaseModel):
    day: date
    page_views: int
    unique_visitors: int
    shared_unique_visitors: int


class TrafficSite(BaseModel):
    site_key: TrafficSiteKey
    name: str
    status: Literal["disabled", "not_connected", "no_activity", "collecting", "stale"]
    last_received_at: datetime | None = None
    page_views: int | None = None
    unique_visitors: int | None = None
    actions: int | None = None


class TrafficSource(BaseModel):
    source_type: str
    source_name: str
    page_views: int
    unique_visitors: int


class TrafficPage(BaseModel):
    site_key: TrafficSiteKey
    path: str
    page_views: int
    unique_visitors: int


class TrafficAction(BaseModel):
    site_key: TrafficSiteKey
    event_name: TrafficEventName
    path: str
    count: int
    unique_visitors: int


class TrafficRetention(BaseModel):
    eligible_visitors: int = 0
    returned_visitors: int = 0
    rate: float | None = None
    cohort_start: date | None = None
    cohort_end: date | None = None


class TrafficQueueStatus(BaseModel):
    status: Literal["disabled", "ok", "full", "unavailable"]
    pending: int | None = None
    dropped_events: int | None = None


class TrafficOverviewResponse(BaseModel):
    enabled: bool
    status: Literal["disabled", "not_connected", "ready"]
    start_date: date
    end_date: date
    site_key: TrafficSelection
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    generated_at: datetime
    data_through: datetime | None = None
    last_ingested_at: datetime | None = None
    collection_started_at: datetime | None = None
    cache_seconds: int = 300
    queue: TrafficQueueStatus
    totals: TrafficMetrics = Field(default_factory=TrafficMetrics)
    previous: TrafficMetrics = Field(default_factory=TrafficMetrics)
    series: list[TrafficPoint] = Field(default_factory=list)
    sites: list[TrafficSite] = Field(default_factory=list)
    traffic_sources: list[TrafficSource] = Field(default_factory=list)
    top_pages: list[TrafficPage] = Field(default_factory=list)
    top_actions: list[TrafficAction] = Field(default_factory=list)
    retention: TrafficRetention = Field(default_factory=TrafficRetention)
