from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

JournalMood = Literal[
    "happy",
    "focused",
    "calm",
    "cozy",
    "inspired",
    "tired",
    "rainy",
    "celebrate",
]
JournalWeather = Literal["sunny", "cloudy", "breezy", "rainy", "snowy", "night"]
JournalVisibility = Literal["public", "private"]
JournalCardTheme = Literal["paper", "sky", "mint", "sunset", "lavender", "grid"]
SpaceCoverPreset = Literal["aurora", "sunset", "meadow", "paper", "starlight"]
LedgerKind = Literal["expense", "income"]
LedgerCategory = Literal[
    "dining",
    "coffee",
    "gaming",
    "shopping",
    "transit",
    "entertainment",
    "housing",
    "salary",
    "other",
]
LedgerPaymentMethod = Literal["wechat", "alipay", "card", "cash"]


class SpaceChecklistItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=240)
    done: bool = False


class SpaceSettingResponse(ORMModel):
    user_id: str
    space_title: str = ""
    space_subtitle: str = ""
    cover_preset: SpaceCoverPreset = "aurora"
    monthly_budget_cents: int = 300000


class SpaceSettingUpdateRequest(BaseModel):
    space_title: str = Field(default="", max_length=80)
    space_subtitle: str = Field(default="", max_length=200)
    cover_preset: SpaceCoverPreset = "aurora"
    monthly_budget_cents: int = Field(default=300000, ge=0, le=100_000_000)


class SpaceJournalCreateRequest(BaseModel):
    entry_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    title: str = Field(default="", max_length=160)
    content: str = Field(min_length=1, max_length=8000)
    mood: JournalMood = "happy"
    weather: JournalWeather = "sunny"
    location: str = Field(default="", max_length=80)
    visibility: JournalVisibility = "public"
    is_pinned: bool = False
    card_theme: JournalCardTheme = "paper"
    tags: list[str] = Field(default_factory=list, max_length=12)
    media_urls: list[str] = Field(default_factory=list, max_length=9)
    checklist: list[SpaceChecklistItem] = Field(default_factory=list, max_length=20)
    ledger_snapshot: dict[str, Any] | None = None


class SpaceJournalUpdateRequest(BaseModel):
    entry_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    title: str | None = Field(default=None, max_length=160)
    content: str | None = Field(default=None, min_length=1, max_length=8000)
    mood: JournalMood | None = None
    weather: JournalWeather | None = None
    location: str | None = Field(default=None, max_length=80)
    visibility: JournalVisibility | None = None
    is_pinned: bool | None = None
    card_theme: JournalCardTheme | None = None
    tags: list[str] | None = Field(default=None, max_length=12)
    media_urls: list[str] | None = Field(default=None, max_length=9)
    checklist: list[SpaceChecklistItem] | None = Field(default=None, max_length=20)
    ledger_snapshot: dict[str, Any] | None = None


class SpaceJournalAuthorBrief(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    level: int = 0


class SpaceJournalItemResponse(ORMModel):
    id: str
    user_id: str
    entry_date: str
    title: str
    content: str
    mood: str
    weather: str
    location: str
    visibility: str
    is_pinned: bool
    card_theme: str
    tags: list[str]
    media_urls: list[str]
    checklist: list[dict[str, Any]]
    ledger_snapshot: dict[str, Any] | None = None
    likes_count: int = 0
    created_at: datetime
    updated_at: datetime
    author: SpaceJournalAuthorBrief | None = None


class SpaceLedgerCreateRequest(BaseModel):
    entry_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    kind: LedgerKind = "expense"
    amount_cents: int = Field(ge=1, le=100_000_000)
    category: LedgerCategory = "dining"
    note: str = Field(default="", max_length=200)
    payment_method: LedgerPaymentMethod = "wechat"


class SpaceLedgerItemResponse(ORMModel):
    id: str
    user_id: str
    entry_date: str
    kind: str
    amount_cents: int
    category: str
    note: str
    payment_method: str
    created_at: datetime
    updated_at: datetime


class SpaceLedgerCategoryBreakdown(BaseModel):
    category: str
    amount_cents: int
    count: int
    ratio_percent: int


class SpaceLedgerMonthlySummary(BaseModel):
    month: str
    total_expense_cents: int = 0
    total_income_cents: int = 0
    monthly_budget_cents: int = 300000
    entry_count: int = 0
    category_breakdown: list[SpaceLedgerCategoryBreakdown] = Field(default_factory=list)


class SpaceMyWorkspaceResponse(BaseModel):
    settings: SpaceSettingResponse
    journals: list[SpaceJournalItemResponse]
    ledger_entries: list[SpaceLedgerItemResponse]
    ledger_summary: SpaceLedgerMonthlySummary


class SpacePublicProfileResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    space_title: str = ""
    space_subtitle: str = ""
    cover_preset: str = "aurora"
    public_journal_count: int = 0
    journals: list[SpaceJournalItemResponse] = Field(default_factory=list)
