from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.ai import AiTopicSummary
from app.schemas.common import ORMModel


class TopicAiSummaryResponse(ORMModel):
    topic_id: str
    summary: str
    key_points: list[str]
    key_post_ids: list[str]
    model_name: str
    cost_units: int
    refreshed_by_id: str | None = None
    generated_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, summary: AiTopicSummary) -> TopicAiSummaryResponse:
        return cls(
            topic_id=summary.topic_id,
            summary=summary.summary,
            key_points=list(summary.key_points or []),
            key_post_ids=list(summary.key_post_ids or []),
            model_name=summary.model_name,
            cost_units=summary.cost_units,
            refreshed_by_id=summary.refreshed_by_id,
            generated_at=summary.generated_at,
            updated_at=summary.updated_at,
        )


class SimilarTopicsRequest(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    raw_md: str = Field(default="", max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=5, ge=1, le=10)


class SimilarTopicResponse(BaseModel):
    id: str
    title: str
    slug: str
    board_slug: str
    board_name: str
    score: float
    matched_terms: list[str]
    excerpt: str


class ModerationAdviceRequest(BaseModel):
    target_type: Literal["topic", "post", "profile", "message"] | str = "post"
    title: str | None = Field(default=None, max_length=180)
    raw_text: str = Field(min_length=1, max_length=8000)
    reason: str | None = Field(default=None, max_length=500)


class ModerationAdviceResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    summary: str
    reasons: list[str]
    suggested_actions: list[str]
    requires_human_review: bool = True
    auto_action_allowed: bool = False
    cost_units: int
