from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SitemapUrl(BaseModel):
    loc: str
    lastmod: datetime | None = None
    changefreq: Literal["daily", "weekly", "monthly"] = "weekly"
    priority: float = Field(default=0.5, ge=0, le=1)


class SeoMetaResponse(BaseModel):
    title: str
    description: str
    canonical_url: str
    robots: str = "index,follow"
    og_type: str = "website"
    og_title: str
    og_description: str
    og_url: str
    twitter_card: str = "summary"
