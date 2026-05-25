from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class MigrationUserRecord(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=80)


class MigrationBoardRecord(BaseModel):
    slug: str = Field(min_length=2, max_length=96)
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="Imported board", max_length=2000)
    color: str = "#3B82F6"


class MigrationTopicRecord(BaseModel):
    external_id: str | None = Field(default=None, max_length=120)
    board_slug: str = Field(min_length=1, max_length=96)
    author_username: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=2, max_length=180)
    slug: str | None = Field(default=None, max_length=220)
    tags: list[str] = Field(default_factory=list, max_length=20)
    raw_md: str = Field(default="", max_length=20000)
    created_at: datetime | None = None


class MigrationPostRecord(BaseModel):
    topic_external_id: str | None = Field(default=None, max_length=120)
    topic_slug: str | None = Field(default=None, max_length=220)
    board_slug: str = Field(min_length=1, max_length=96)
    author_username: str = Field(min_length=1, max_length=32)
    post_number: int = Field(ge=1)
    raw_md: str = Field(min_length=1, max_length=20000)
    created_at: datetime | None = None


class MigrationImportRequest(BaseModel):
    source: str = Field(default="json", max_length=80)
    users: list[MigrationUserRecord] = Field(default_factory=list, max_length=500)
    boards: list[MigrationBoardRecord] = Field(default_factory=list, max_length=200)
    topics: list[MigrationTopicRecord] = Field(default_factory=list, max_length=1000)
    posts: list[MigrationPostRecord] = Field(default_factory=list, max_length=5000)


class MigrationRowResult(BaseModel):
    resource: Literal["user", "board", "topic", "post", "tag"] | str
    key: str
    action: Literal["created", "updated", "skipped", "error"] | str
    message: str


class MigrationImportResponse(BaseModel):
    dry_run: bool
    source: str
    created: int
    updated: int
    skipped: int
    errors: int
    rows: list[MigrationRowResult]


class MigrationExportResponse(BaseModel):
    exported_at: datetime
    users: list[dict[str, object]]
    boards: list[dict[str, object]]
    topics: list[dict[str, object]]
    posts: list[dict[str, object]]
    tags: list[dict[str, object]]
