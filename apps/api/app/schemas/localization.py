from __future__ import annotations

from pydantic import BaseModel, Field


class TopicLocalizationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=180)


class TopicLocalizationResponse(BaseModel):
    topic_id: str
    locale: str
    title: str
    fallback_title: str
    fallback_used: bool
    available_locales: list[str] = Field(default_factory=list)
