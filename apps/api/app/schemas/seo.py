from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SitemapUrl(BaseModel):
    loc: str
    lastmod: datetime | None = None


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
