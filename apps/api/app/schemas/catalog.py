from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CatalogDestinationKind = Literal["external", "internal"]
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


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
    icon_upload_id: str | None = None
    sort_order: int = 0
    is_visible: bool = True

    @field_validator("name", "url", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CatalogProjectUpdateRequest(BaseModel):
    category_id: str | None = None
    slug: str | None = Field(default=None, min_length=1, max_length=80, pattern=SLUG_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    kind: CatalogDestinationKind | None = None
    description: str | None = Field(default=None, max_length=300)
    icon_upload_id: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None

    @field_validator("name", "url", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CatalogRatingCreateRequest(BaseModel):
    score: int = Field(ge=1, le=5)


class CatalogRatingStateResponse(BaseModel):
    project_id: str
    average_score: float | None
    rating_count: int
    my_score: int | None


class CatalogProjectResponse(BaseModel):
    id: str
    slug: str
    name: str
    url: str
    kind: CatalogDestinationKind
    description: str | None
    icon_url: str | None
    created_at: datetime
    average_score: float | None
    rating_count: int
    my_score: int | None


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
