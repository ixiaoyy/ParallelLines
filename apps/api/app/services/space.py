from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, noload

from app.core.exceptions import PermissionDeniedError, NotFoundError
from app.db.base import SHANGHAI_TZ, utcnow
from app.models.space import SpaceJournalEntry, SpaceLedgerEntry, SpaceSetting
from app.models.user import User
from app.schemas.space import (
    SpaceJournalAuthorBrief,
    SpaceJournalCreateRequest,
    SpaceJournalItemResponse,
    SpaceJournalUpdateRequest,
    SpaceLedgerCategoryBreakdown,
    SpaceLedgerCreateRequest,
    SpaceLedgerItemResponse,
    SpaceLedgerMonthlySummary,
    SpaceMyWorkspaceResponse,
    SpacePublicProfileResponse,
    SpaceSettingResponse,
    SpaceSettingUpdateRequest,
)


def _current_month_str() -> str:
    return datetime.now(SHANGHAI_TZ).strftime("%Y-%m")


def _clean_tags(raw_tags: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in raw_tags:
        normalized = tag.strip().lstrip("#").strip()
        if not normalized or len(normalized) > 32 or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= 12:
            break
    return cleaned


def _author_brief(user: User | None) -> SpaceJournalAuthorBrief | None:
    if not user:
        return None
    return SpaceJournalAuthorBrief(
        id=str(user.id),
        username=user.username,
        display_name=getattr(user, "display_name", None),
        avatar_url=user.avatar_url,
        level=user.level,
    )


def _serialize_journal(entry: SpaceJournalEntry, author: User | None = None) -> SpaceJournalItemResponse:
    resolved_author = author or getattr(entry, "user", None)
    return SpaceJournalItemResponse(
        id=str(entry.id),
        user_id=str(entry.user_id),
        entry_date=entry.entry_date,
        title=entry.title or "",
        content=entry.content,
        mood=entry.mood or "happy",
        weather=entry.weather or "sunny",
        location=entry.location or "",
        visibility=entry.visibility or "public",
        is_pinned=bool(entry.is_pinned),
        card_theme=entry.card_theme or "paper",
        tags=list(entry.tags or []),
        media_urls=list(entry.media_urls or []),
        checklist=list(entry.checklist or []),
        ledger_snapshot=entry.ledger_snapshot,
        likes_count=int(entry.likes_count or 0),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        author=_author_brief(resolved_author),
    )


class SpaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_settings(self, user_id: str) -> SpaceSettingResponse:
        try:
            setting = await self.session.scalar(
                select(SpaceSetting)
                .options(noload(SpaceSetting.user))
                .where(SpaceSetting.user_id == user_id)
            )
            if setting:
                return SpaceSettingResponse.model_validate(setting)
        except (OperationalError, ProgrammingError):
            await self.session.rollback()
            return SpaceSettingResponse(user_id=user_id)

        return SpaceSettingResponse(user_id=user_id)

    async def update_settings(
        self, user_id: str, payload: SpaceSettingUpdateRequest
    ) -> SpaceSettingResponse:
        setting = await self.session.scalar(
            select(SpaceSetting).where(SpaceSetting.user_id == user_id)
        )
        if not setting:
            setting = SpaceSetting(
                user_id=user_id,
                space_title=payload.space_title.strip(),
                space_subtitle=payload.space_subtitle.strip(),
                cover_preset=payload.cover_preset,
                monthly_budget_cents=payload.monthly_budget_cents,
            )
            self.session.add(setting)
        else:
            setting.space_title = payload.space_title.strip()
            setting.space_subtitle = payload.space_subtitle.strip()
            setting.cover_preset = payload.cover_preset
            setting.monthly_budget_cents = payload.monthly_budget_cents
            setting.updated_at = utcnow()

        await self.session.commit()
        await self.session.refresh(setting)
        return SpaceSettingResponse.model_validate(setting)

    async def get_my_workspace(
        self, current_user: User, month: str | None = None
    ) -> SpaceMyWorkspaceResponse:
        target_month = month if month and len(month) == 7 else _current_month_str()
        settings = await self.get_or_create_settings(current_user.id)

        try:
            journal_stmt = (
                select(SpaceJournalEntry)
                .options(noload(SpaceJournalEntry.user))
                .where(SpaceJournalEntry.user_id == current_user.id)
                .order_by(
                    SpaceJournalEntry.is_pinned.desc(),
                    SpaceJournalEntry.entry_date.desc(),
                    SpaceJournalEntry.created_at.desc(),
                )
                .limit(200)
            )
            journals = list(await self.session.scalars(journal_stmt))

            ledger_stmt = (
                select(SpaceLedgerEntry)
                .options(noload(SpaceLedgerEntry.user))
                .where(
                    SpaceLedgerEntry.user_id == current_user.id,
                    SpaceLedgerEntry.entry_date.like(f"{target_month}-%"),
                )
                .order_by(
                    SpaceLedgerEntry.entry_date.desc(),
                    SpaceLedgerEntry.created_at.desc(),
                )
                .limit(500)
            )
            ledgers = list(await self.session.scalars(ledger_stmt))
        except (OperationalError, ProgrammingError):
            await self.session.rollback()
            journals = []
            ledgers = []

        serialized_journals = [_serialize_journal(item, current_user) for item in journals]
        serialized_ledgers = [SpaceLedgerItemResponse.model_validate(item) for item in ledgers]
        summary = self._compute_monthly_summary(
            ledgers=ledgers,
            month=target_month,
            monthly_budget_cents=settings.monthly_budget_cents,
        )
        return SpaceMyWorkspaceResponse(
            settings=settings,
            journals=serialized_journals,
            ledger_entries=serialized_ledgers,
            ledger_summary=summary,
        )

    def _compute_monthly_summary(
        self,
        ledgers: list[SpaceLedgerEntry],
        month: str,
        monthly_budget_cents: int,
    ) -> SpaceLedgerMonthlySummary:
        month_prefix = f"{month}-"
        month_entries = [item for item in ledgers if item.entry_date.startswith(month_prefix)]

        total_expense = 0
        total_income = 0
        category_totals: dict[str, int] = defaultdict(int)
        category_counts: dict[str, int] = defaultdict(int)

        for item in month_entries:
            if item.kind == "income":
                total_income += int(item.amount_cents)
            else:
                total_expense += int(item.amount_cents)
                category_totals[item.category] += int(item.amount_cents)
                category_counts[item.category] += 1

        breakdown: list[SpaceLedgerCategoryBreakdown] = []
        for cat, amount in sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True):
            ratio = round((amount * 100) / total_expense) if total_expense > 0 else 0
            breakdown.append(
                SpaceLedgerCategoryBreakdown(
                    category=cat,
                    amount_cents=amount,
                    count=category_counts[cat],
                    ratio_percent=max(1, ratio) if amount > 0 else 0,
                )
            )

        return SpaceLedgerMonthlySummary(
            month=month,
            total_expense_cents=total_expense,
            total_income_cents=total_income,
            monthly_budget_cents=monthly_budget_cents,
            entry_count=len(month_entries),
            category_breakdown=breakdown,
        )

    async def create_journal(
        self, current_user: User, payload: SpaceJournalCreateRequest
    ) -> SpaceJournalItemResponse:
        entry = SpaceJournalEntry(
            user_id=current_user.id,
            entry_date=payload.entry_date,
            title=payload.title.strip(),
            content=payload.content.strip(),
            mood=payload.mood,
            weather=payload.weather,
            location=payload.location.strip(),
            visibility=payload.visibility,
            is_pinned=payload.is_pinned,
            card_theme=payload.card_theme,
            tags=_clean_tags(payload.tags),
            media_urls=[url.strip() for url in payload.media_urls if url.strip()][:9],
            checklist=[item.model_dump() for item in payload.checklist],
            ledger_snapshot=payload.ledger_snapshot,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return _serialize_journal(entry, current_user)

    async def update_journal(
        self, current_user: User, entry_id: str, payload: SpaceJournalUpdateRequest
    ) -> SpaceJournalItemResponse:
        entry = await self.session.get(SpaceJournalEntry, entry_id)
        if not entry:
            raise NotFoundError(code="journal_not_found", message="手账记录不存在。")
        if str(entry.user_id) != str(current_user.id):
            raise PermissionDeniedError(code="journal_forbidden", message="无权修改他人的手账记录。")

        if payload.entry_date is not None:
            entry.entry_date = payload.entry_date
        if payload.title is not None:
            entry.title = payload.title.strip()
        if payload.content is not None:
            entry.content = payload.content.strip()
        if payload.mood is not None:
            entry.mood = payload.mood
        if payload.weather is not None:
            entry.weather = payload.weather
        if payload.location is not None:
            entry.location = payload.location.strip()
        if payload.visibility is not None:
            entry.visibility = payload.visibility
        if payload.is_pinned is not None:
            entry.is_pinned = payload.is_pinned
        if payload.card_theme is not None:
            entry.card_theme = payload.card_theme
        if payload.tags is not None:
            entry.tags = _clean_tags(payload.tags)
        if payload.media_urls is not None:
            entry.media_urls = [url.strip() for url in payload.media_urls if url.strip()][:9]
        if payload.checklist is not None:
            entry.checklist = [item.model_dump() for item in payload.checklist]
        if payload.ledger_snapshot is not None:
            entry.ledger_snapshot = payload.ledger_snapshot

        entry.updated_at = utcnow()
        await self.session.commit()
        await self.session.refresh(entry)
        return _serialize_journal(entry, current_user)

    async def delete_journal(self, current_user: User, entry_id: str) -> bool:
        entry = await self.session.get(SpaceJournalEntry, entry_id)
        if not entry:
            raise NotFoundError(code="journal_not_found", message="手账记录不存在。")
        if str(entry.user_id) != str(current_user.id):
            raise PermissionDeniedError(code="journal_forbidden", message="无权删除他人的手账记录。")
        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def like_journal(
        self, entry_id: str, viewer: User | None = None
    ) -> SpaceJournalItemResponse:
        entry = await self.session.get(SpaceJournalEntry, entry_id)
        if not entry:
            raise NotFoundError(code="journal_not_found", message="手账记录不存在。")
        if entry.visibility != "public" and (not viewer or str(viewer.id) != str(entry.user_id)):
            raise NotFoundError(code="journal_not_found", message="手账记录不存在。")
        # 使用 SQL 原子自增，避免并发点赞覆盖增量。
        await self.session.execute(
            update(SpaceJournalEntry)
            .where(SpaceJournalEntry.id == entry.id)
            .values(likes_count=SpaceJournalEntry.likes_count + 1)
        )
        await self.session.commit()
        await self.session.refresh(entry)
        # 显式读取作者，避免异步会话中触发关系懒加载。
        author = await self.session.get(User, entry.user_id)
        return _serialize_journal(entry, author)

    async def create_ledger_entry(
        self, current_user: User, payload: SpaceLedgerCreateRequest
    ) -> SpaceLedgerItemResponse:
        entry = SpaceLedgerEntry(
            user_id=current_user.id,
            entry_date=payload.entry_date,
            kind=payload.kind,
            amount_cents=payload.amount_cents,
            category=payload.category,
            note=payload.note.strip(),
            payment_method=payload.payment_method,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return SpaceLedgerItemResponse.model_validate(entry)

    async def delete_ledger_entry(self, current_user: User, entry_id: str) -> bool:
        entry = await self.session.get(SpaceLedgerEntry, entry_id)
        if not entry:
            raise NotFoundError(code="ledger_not_found", message="账单记录不存在。")
        if str(entry.user_id) != str(current_user.id):
            raise PermissionDeniedError(code="ledger_forbidden", message="无权删除他人的账单记录。")
        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def get_public_user_space(
        self, identifier: str, viewer: User | None = None
    ) -> SpacePublicProfileResponse:
        user_stmt = select(User).where(
            or_(User.username == identifier, User.id == identifier)
            if identifier.isdigit()
            else (User.username == identifier)
        )
        user = await self.session.scalar(user_stmt)
        if not user or user.status == "deleted":
            raise NotFoundError(code="user_not_found", message="成员不存在。")

        is_owner = bool(viewer and str(viewer.id) == str(user.id))
        settings = await self.get_or_create_settings(user.id)

        try:
            conditions: list[Any] = [SpaceJournalEntry.user_id == user.id]
            if not is_owner:
                conditions.append(SpaceJournalEntry.visibility == "public")

            stmt = (
                select(SpaceJournalEntry)
                .options(noload(SpaceJournalEntry.user))
                .where(*conditions)
                .order_by(
                    SpaceJournalEntry.is_pinned.desc(),
                    SpaceJournalEntry.entry_date.desc(),
                    SpaceJournalEntry.created_at.desc(),
                )
                .limit(100)
            )
            entries = list(await self.session.scalars(stmt))
            public_count_stmt = select(func.count(SpaceJournalEntry.id)).where(
                SpaceJournalEntry.user_id == user.id,
                SpaceJournalEntry.visibility == "public",
            )
            public_count = int((await self.session.scalar(public_count_stmt)) or 0)
        except (OperationalError, ProgrammingError):
            await self.session.rollback()
            entries = []
            public_count = 0

        return SpacePublicProfileResponse(
            user_id=str(user.id),
            username=user.username,
            display_name=getattr(user, "display_name", None),
            avatar_url=user.avatar_url,
            bio=getattr(user, "bio", None),
            space_title=settings.space_title,
            space_subtitle=settings.space_subtitle,
            cover_preset=settings.cover_preset,
            public_journal_count=public_count,
            journals=[_serialize_journal(item, user) for item in entries],
        )

    async def list_public_feed(self, limit: int = 40) -> list[SpaceJournalItemResponse]:
        try:
            stmt = (
                select(SpaceJournalEntry)
                .join(User, User.id == SpaceJournalEntry.user_id)
                .options(contains_eager(SpaceJournalEntry.user))
                .where(
                    SpaceJournalEntry.visibility == "public",
                    User.status == "active",
                )
                .order_by(
                    SpaceJournalEntry.created_at.desc(),
                )
                .limit(limit)
            )
            entries = list((await self.session.scalars(stmt)).unique())
            return [_serialize_journal(item) for item in entries]
        except (OperationalError, ProgrammingError):
            await self.session.rollback()
            return []
