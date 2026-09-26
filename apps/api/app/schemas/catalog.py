from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

CatalogDestinationKind = Literal["external", "internal"]
CatalogSubmissionStatus = Literal["pending", "approved", "rejected"]
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


# 作者链接会在公开卡片中打开；仅保存没有凭据和控制字符的 HTTPS 公网域名。
def _validated_author_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if "\\" in value or any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise ValueError("Invalid HTTPS author URL")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid HTTPS author URL") from exc
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port == 0
    ):
        raise ValueError("Invalid HTTPS author URL")
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Invalid HTTPS author URL") from exc
    labels = ascii_hostname.split(".")
    if (
        len(ascii_hostname) > 253
        or len(labels) < 2
        or labels[-1].isdigit()
        or labels[-1] in {"local", "localhost", "internal", "test", "invalid", "example", "onion"}
        or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
            for label in labels
        )
    ):
        raise ValueError("Invalid HTTPS author URL")
    return value


class CatalogCategoryCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=80, pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    icon_upload_id: str | None = None
    sort_order: int = 0
    is_visible: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class CatalogCategoryUpdateRequest(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=80, pattern=SLUG_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon_upload_id: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CatalogProjectCreateRequest(BaseModel):
    category_id: str
    slug: str = Field(min_length=1, max_length=80, pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    kind: CatalogDestinationKind
    description: str | None = Field(default=None, max_length=300)
    author_name: str | None = Field(default=None, max_length=120)
    author_url: str | None = Field(default=None, max_length=2048)
    icon_upload_id: str | None = None
    sort_order: int = 0
    is_visible: bool = True

    @field_validator("name", "url", "description", "author_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("author_url")
    @classmethod
    def validate_author_url(cls, value: str | None) -> str | None:
        return _validated_author_url(value)


class CatalogProjectUpdateRequest(BaseModel):
    category_id: str | None = None
    slug: str | None = Field(default=None, min_length=1, max_length=80, pattern=SLUG_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    kind: CatalogDestinationKind | None = None
    description: str | None = Field(default=None, max_length=300)
    author_name: str | None = Field(default=None, max_length=120)
    author_url: str | None = Field(default=None, max_length=2048)
    icon_upload_id: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None

    @field_validator("name", "url", "description", "author_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("author_url")
    @classmethod
    def validate_author_url(cls, value: str | None) -> str | None:
        return _validated_author_url(value)


class CatalogRatingCreateRequest(BaseModel):
    score: int = Field(ge=1, le=5)


# 投稿表单只要求分类、项目和 HTTPS 地址；署名与联系方式可留空。
class CatalogSubmissionCreateRequest(BaseModel):
    category_name: str = Field(min_length=1, max_length=120)
    project_name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=9, max_length=2048, pattern=r"^https://")
    author_name: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=200)

    @field_validator("category_name", "project_name", "url", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("author_name", "contact", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class CatalogSubmissionCreateResponse(BaseModel):
    id: str
    status: CatalogSubmissionStatus


class CatalogSubmissionReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]


# 联系方式只出现在管理员审核响应，不进入公开项目响应。
class AdminCatalogSubmissionResponse(BaseModel):
    id: str
    category_name: str
    project_name: str
    url: str
    author_name: str | None
    contact: str | None
    cover_url: str | None
    status: CatalogSubmissionStatus
    project_id: str | None
    reviewed_by_id: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CatalogRatingStateResponse(BaseModel):
    project_id: str
    average_score: float | None
    rating_count: int
    rating_score_sum: int
    my_score: int | None


class CatalogViewStateResponse(BaseModel):
    project_id: str
    view_count: int


class CatalogProjectResponse(BaseModel):
    id: str
    slug: str
    name: str
    url: str
    kind: CatalogDestinationKind
    description: str | None
    author_name: str | None
    author_url: str | None
    icon_url: str | None
    created_at: datetime
    average_score: float | None
    rating_count: int
    rating_score_sum: int
    my_score: int | None
    view_count: int = 0


class CatalogCategoryResponse(BaseModel):
    id: str
    slug: str
    name: str
    icon_url: str | None
    projects: list[CatalogProjectResponse]


class CatalogResponse(BaseModel):
    categories: list[CatalogCategoryResponse]


class AdminCatalogProjectResponse(CatalogProjectResponse):
    category_id: str
    icon_upload_id: str | None
    sort_order: int
    is_visible: bool
    updated_at: datetime


class AdminCatalogCategoryResponse(BaseModel):
    id: str
    slug: str
    name: str
    icon_upload_id: str | None
    icon_url: str | None
    sort_order: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime
    projects: list[AdminCatalogProjectResponse]


class AdminCatalogResponse(BaseModel):
    categories: list[AdminCatalogCategoryResponse]
