from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.news import FrontierNewsItem, FrontierNewsSource
from app.schemas.common import ORMModel

FrontierNewsSourceKind = Literal[
    "rss",
    "arxiv",
    "hacker_news",
    "github_search",
    "xai_news",
    "arena_leaderboard",
]
FrontierNewsItemStatus = Literal[
    "collected",
    "ai_pending",
    "review_pending",
    "published",
    "rejected",
    "duplicate",
    "failed",
]


class FrontierNewsSourceCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=96)
    name: str = Field(min_length=2, max_length=120)
    kind: FrontierNewsSourceKind
    url: str = Field(min_length=8, max_length=1024)
    config: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True
    trust_level: int = Field(default=50, ge=0, le=100)
    fetch_interval_minutes: int = Field(default=60, ge=5, le=24 * 60)


class FrontierNewsSourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    url: str | None = Field(default=None, min_length=8, max_length=1024)
    config: dict[str, object] | None = None
    enabled: bool | None = None
    trust_level: int | None = Field(default=None, ge=0, le=100)
    fetch_interval_minutes: int | None = Field(default=None, ge=5, le=24 * 60)


class FrontierNewsSourceResponse(ORMModel):
    id: str
    key: str
    name: str
    kind: str
    url: str
    config: dict[str, object]
    enabled: bool
    trust_level: int
    fetch_interval_minutes: int
    last_checked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, source: FrontierNewsSource) -> FrontierNewsSourceResponse:
        """Build an API-safe representation of a white-listed frontier news source."""

        return cls(
            id=source.id,
            key=source.key,
            name=source.name,
            kind=source.kind,
            url=source.url,
            config=source.config,
            enabled=source.enabled,
            trust_level=source.trust_level,
            fetch_interval_minutes=source.fetch_interval_minutes,
            last_checked_at=source.last_checked_at,
            last_error=source.last_error,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )


class FrontierNewsItemResponse(ORMModel):
    id: str
    source_id: str
    source_name: str | None = None
    external_id: str
    canonical_url: str
    title: str
    summary: str | None = None
    author_names: list[str]
    published_at: datetime | None = None
    item_type: str
    suggested_tags: list[str]
    ai_title_zh: str | None = None
    ai_summary_zh: str | None = None
    ai_key_points: list[str]
    ai_why_it_matters: str | None = None
    ai_risk_flags: list[str]
    ai_review_suggestion: str | None = None
    ai_model_name: str | None = None
    ai_processed_at: datetime | None = None
    ai_error: str | None = None
    score: int
    status: str
    reviewable_id: str | None = None
    topic_id: str | None = None
    reviewed_by_id: str | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, item: FrontierNewsItem) -> FrontierNewsItemResponse:
        """Build the admin-facing material view without exposing raw payload internals."""

        return cls(
            id=item.id,
            source_id=item.source_id,
            source_name=item.source.name if item.source else None,
            external_id=item.external_id,
            canonical_url=item.canonical_url,
            title=item.title,
            summary=item.summary,
            author_names=item.author_names,
            published_at=item.published_at,
            item_type=item.item_type,
            suggested_tags=item.suggested_tags,
            ai_title_zh=item.ai_title_zh,
            ai_summary_zh=item.ai_summary_zh,
            ai_key_points=item.ai_key_points,
            ai_why_it_matters=item.ai_why_it_matters,
            ai_risk_flags=item.ai_risk_flags,
            ai_review_suggestion=item.ai_review_suggestion,
            ai_model_name=item.ai_model_name,
            ai_processed_at=item.ai_processed_at,
            ai_error=item.ai_error,
            score=item.score,
            status=item.status,
            reviewable_id=item.reviewable_id,
            topic_id=item.topic_id,
            reviewed_by_id=item.reviewed_by_id,
            reviewed_by_name=item.reviewed_by.username if item.reviewed_by else None,
            reviewed_at=item.reviewed_at,
            review_note=item.review_note,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class FrontierNewsItemQueueRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2_000)


class FrontierNewsCollectResponse(BaseModel):
    source_count: int
    created_count: int
    queued_count: int
    skipped_count: int
    error_count: int
