from __future__ import annotations

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.security import hash_password
from app.db.base import SHANGHAI_TZ, as_utc_datetime, utcnow
from app.models.forum import Board, Post, Topic
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.forum import TopicCreateRequest
from app.services.daily_reading_provider import (
    DailyReadingDraft,
    generate_daily_reading_with_fallback,
    parse_daily_reading_drafts,
)
from app.services.forum import ForumService

DAILY_READING_USERNAME = "页边有光"
DAILY_READING_EMAIL = "page-margin-light@pingxingxian.space"
DAILY_READING_AVATAR_URL = "/avatars/page-margin-light.png"
DAILY_READING_BIO = "动画游戏都玩一点，偶尔记下读完几页后的想法。"
DAILY_READING_BOARD_SLUG = "reading"
DAILY_READING_AUDIT_ACTION = "daily_reading_topic_published"
DAILY_READING_AUDIT_TARGET = "daily_reading_seed"
DAILY_READING_PLAN_ACTION = "daily_reading_day_planned"
DAILY_READING_PLAN_TARGET = "daily_reading_plan"
DAILY_READING_TOPIC_COUNT = 2


@dataclass(frozen=True)
class DailyReadingPlan:
    """Store one date-bound reading topic plan and its provider provenance."""

    seed_key: str
    planned_date: date
    slot: int
    title: str
    raw_md: str
    tags: tuple[str, ...]
    model_name: str
    provider_mode: str

    def to_preview(self) -> dict[str, object]:
        """Return a JSON-safe full preview for CLI and background-job results."""

        return {
            "seed_key": self.seed_key,
            "planned_date": self.planned_date.isoformat(),
            "slot": self.slot,
            "author": DAILY_READING_USERNAME,
            "board_slug": DAILY_READING_BOARD_SLUG,
            "title": self.title,
            "raw_md": self.raw_md,
            "tags": list(self.tags),
            "model_name": self.model_name,
            "provider_mode": self.provider_mode,
        }


@dataclass(frozen=True)
class DailyReadingPublishResult:
    """Summarize one planned daily reading topic after a publish attempt."""

    seed_key: str
    slot: int
    title: str
    status: str
    topic_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe result dictionary without side effects."""

        return {
            "seed_key": self.seed_key,
            "slot": self.slot,
            "title": self.title,
            "status": self.status,
            "topic_id": self.topic_id,
            "reason": self.reason,
        }


class DailyReadingService:
    """Plan and publish two persona-authored reading reflections per local day.

    Key dependencies are an async database session and optional runtime settings.
    Public methods return JSON-safe summaries. Write-mode side effects include
    persona upserts, canonical forum topic creation, and idempotency audit logs.
    """

    def __init__(self, session: AsyncSession | None, settings: Settings | None = None) -> None:
        """Store the optional session and resolved runtime settings without I/O."""

        self.session = session
        self.settings = settings or get_settings()

    async def plan_day(
        self,
        planned_date: date | None = None,
        *,
        force_local: bool = False,
    ) -> list[DailyReadingPlan]:
        """Build exactly two reading plans without database writes.

        Key parameters choose the Shanghai calendar date and optional local-only
        generation. Return value is two ordered plans. Side effects are bounded
        audit-log reads and, when configured, one provider request.
        """

        target_date = planned_date or local_today()
        recent_titles = await self._recent_titles()
        generated = await generate_daily_reading_with_fallback(
            self.settings,
            target_date,
            recent_titles,
            force_local=force_local,
        )
        return [
            self._plan_from_draft(
                target_date,
                slot,
                draft,
                model_name=generated.model_name,
                provider_mode=generated.provider_mode,
            )
            for slot, draft in enumerate(generated.drafts, start=1)
        ]

    async def publish_day(
        self,
        planned_date: date | None = None,
        *,
        publish_mode: str | None = None,
        dry_run: bool = False,
        force_local: bool = False,
        slots: Sequence[int] | None = None,
    ) -> dict[str, object]:
        """Preview or publish selected daily reading-reflection slots.

        Key parameters choose date, mode, dry-run behavior, provider path, and
        optional slots. Return value includes selected plans and outcomes. In
        auto mode, side effects create only missing selected topics and audits.
        """

        target_date = planned_date or local_today()
        selected_slots = normalize_daily_reading_slots(slots)
        mode = publish_mode or self.settings.daily_reading_publish_mode
        if mode == "off":
            return {
                "dry_run": True,
                "publish_mode": mode,
                "planned_date": target_date.isoformat(),
                "status": "skipped",
                "reason": "daily_reading_off",
                "plans": [],
                "results": [],
            }
        existing = await self._existing_day_results(target_date)
        existing_by_slot = {result.slot: result for result in existing}
        if not dry_run and mode == "auto" and all(
            slot in existing_by_slot for slot in selected_slots
        ):
            return {
                "dry_run": False,
                "publish_mode": mode,
                "planned_date": target_date.isoformat(),
                "plans": [],
                "results": [existing_by_slot[slot].to_dict() for slot in selected_slots],
            }

        effective_dry_run = dry_run or mode != "auto"
        plans = (
            await self.plan_day(target_date, force_local=force_local)
            if effective_dry_run
            else await self._stored_or_new_plans(target_date, force_local=force_local)
        )
        selected_plans = [plan for plan in plans if plan.slot in selected_slots]
        if effective_dry_run:
            return {
                "dry_run": True,
                "publish_mode": mode,
                "planned_date": target_date.isoformat(),
                "plans": [plan.to_preview() for plan in selected_plans],
                "results": [],
            }

        results_by_seed = {result.seed_key: result for result in existing}
        for plan in selected_plans:
            if plan.seed_key not in results_by_seed:
                results_by_seed[plan.seed_key] = await self._publish_plan(plan)
        results = [results_by_seed[plan.seed_key] for plan in selected_plans]
        return {
            "dry_run": False,
            "publish_mode": mode,
            "planned_date": target_date.isoformat(),
            "plans": [plan.to_preview() for plan in selected_plans],
            "results": [result.to_dict() for result in results],
        }

    async def _stored_or_new_plans(
        self,
        planned_date: date,
        *,
        force_local: bool,
    ) -> list[DailyReadingPlan]:
        """Load the committed daily plan or generate and store it once.

        Key parameters choose the Shanghai date and provider path. Return value
        is the exact two plans reused by every write retry. Side effect: on the
        first auto run, writes one plan audit before any topic is created.
        """

        stored = await self._stored_plans(planned_date)
        if stored is not None:
            return stored
        plans = await self.plan_day(planned_date, force_local=force_local)
        first = plans[0]
        self.session.add(
            AuditLog(
                actor_id=None,
                action=DAILY_READING_PLAN_ACTION,
                target_type=DAILY_READING_PLAN_TARGET,
                target_id=planned_date.isoformat(),
                board_id=None,
                data={
                    "planned_date": planned_date.isoformat(),
                    "model_name": first.model_name,
                    "provider_mode": first.provider_mode,
                    "posts": [
                        {
                            "title": plan.title,
                            "raw_md": plan.raw_md,
                            "tags": list(plan.tags),
                        }
                        for plan in plans
                    ],
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()
        return plans

    async def _stored_plans(self, planned_date: date) -> list[DailyReadingPlan] | None:
        """Decode the latest committed plan audit for one local date.

        Key parameter is the Shanghai calendar date. Return value is two plans
        or none. Side effect: one audit-log read; malformed stored plans fail
        closed so a retry never silently changes already chosen content.
        """

        audit = await self.session.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == DAILY_READING_PLAN_ACTION,
                AuditLog.target_type == DAILY_READING_PLAN_TARGET,
                AuditLog.target_id == planned_date.isoformat(),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if audit is None:
            return None
        data = audit.data or {}
        drafts = parse_daily_reading_drafts({"posts": data.get("posts")})
        model_name = data.get("model_name")
        provider_mode = data.get("provider_mode")
        return [
            self._plan_from_draft(
                planned_date,
                slot,
                draft,
                model_name=(model_name if isinstance(model_name, str) else "unknown")[:120],
                provider_mode=(
                    provider_mode if isinstance(provider_mode, str) else "stored_unknown"
                )[:64],
            )
            for slot, draft in enumerate(drafts, start=1)
        ]

    async def _publish_plan(self, plan: DailyReadingPlan) -> DailyReadingPublishResult:
        """Create one planned topic unless its stable slot audit already exists."""

        existing = await self._existing_result(plan.seed_key, fallback_slot=plan.slot)
        if existing is not None:
            return existing
        board = await self._find_public_reading_board()
        if board is None:
            return DailyReadingPublishResult(
                seed_key=plan.seed_key,
                slot=plan.slot,
                title=plan.title,
                status="skipped",
                reason="missing_public_board:reading",
            )
        try:
            author = await self._ensure_persona()
            recovered_topic = await self._matching_untracked_topic(plan, board, author)
            if recovered_topic is None:
                topic = await ForumService(self.session).create_topic(
                    DAILY_READING_BOARD_SLUG,
                    TopicCreateRequest(
                        title=plan.title,
                        raw_md=plan.raw_md,
                        tags=list(plan.tags),
                    ),
                    author,
                    skip_spam_checks=True,
                    skip_review_queue=True,
                )
            else:
                topic = recovered_topic
            await self._record_publish_audit(plan, topic, board, author)
        except AppError as exc:
            await self.session.rollback()
            return DailyReadingPublishResult(
                seed_key=plan.seed_key,
                slot=plan.slot,
                title=plan.title,
                status="failed",
                reason=exc.code,
            )
        return DailyReadingPublishResult(
            seed_key=plan.seed_key,
            slot=plan.slot,
            title=plan.title,
            status="created" if recovered_topic is None else "recovered",
            topic_id=topic.id,
        )

    async def _existing_day_results(self, planned_date: date) -> list[DailyReadingPublishResult]:
        """Return ordered idempotent outcomes already recorded for one local date."""

        results: list[DailyReadingPublishResult] = []
        for slot in range(1, DAILY_READING_TOPIC_COUNT + 1):
            seed = daily_reading_seed_key(planned_date, slot)
            existing = await self._existing_result(seed, fallback_slot=slot)
            if existing is not None:
                results.append(existing)
        return results

    async def _existing_result(
        self,
        seed_key: str,
        *,
        fallback_slot: int,
    ) -> DailyReadingPublishResult | None:
        """Return the latest recorded publish result for a stable daily slot.

        Key parameters identify the seed and expected slot. The return value is
        present even when the topic was later deleted, preventing automatic
        republishing after moderation. Side effect: one audit-log read.
        """

        audit = await self.session.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == DAILY_READING_AUDIT_ACTION,
                AuditLog.target_type == DAILY_READING_AUDIT_TARGET,
                AuditLog.target_id == seed_key,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if audit is None:
            return None
        data = audit.data or {}
        topic_id = data.get("topic_id")
        title = data.get("title")
        slot = data.get("slot")
        return DailyReadingPublishResult(
            seed_key=seed_key,
            slot=(
                int(slot)
                if isinstance(slot, int | str) and str(slot).isdigit()
                else fallback_slot
            ),
            title=title if isinstance(title, str) and title else seed_key,
            status="existing",
            topic_id=topic_id if isinstance(topic_id, str) and topic_id else None,
        )

    async def _recent_titles(self) -> list[str]:
        """Return a bounded list of recent auto-reading titles for model avoidance."""

        if self.session is None:
            return []
        audits = list(
            await self.session.scalars(
                select(AuditLog)
                .where(AuditLog.action == DAILY_READING_AUDIT_ACTION)
                .order_by(AuditLog.created_at.desc())
                .limit(60)
            )
        )
        return [
            title
            for audit in audits
            if isinstance(title := (audit.data or {}).get("title"), str) and title
        ]

    async def _find_public_reading_board(self) -> Board | None:
        """Return the public reading board or none when it is missing or private."""

        board = await self.session.scalar(
            select(Board).where(Board.slug == DAILY_READING_BOARD_SLUG).limit(1)
        )
        if board is None or board.visibility != "public":
            return None
        return board

    async def _ensure_persona(self) -> User:
        """Create or refresh the dedicated ordinary persona account.

        Return value is the active user row. Side effect may insert or update the
        profile and always persists `is_persona=True`; existing passwords are not
        reset by daily runs.
        """

        existing = await self.session.scalar(
            select(User).where(
                or_(
                    User.username == DAILY_READING_USERNAME,
                    User.email == DAILY_READING_EMAIL,
                )
            )
        )
        if existing is not None:
            if (
                existing.username != DAILY_READING_USERNAME
                or existing.email != DAILY_READING_EMAIL
            ):
                raise ValidationError(
                    "daily_reading_persona_conflict",
                    "Daily reading persona identity conflicts with an existing user",
                    {
                        "username": DAILY_READING_USERNAME,
                        "email": DAILY_READING_EMAIL,
                    },
                )
            if existing.role == "admin":
                raise ValidationError(
                    "daily_reading_persona_admin_conflict",
                    "An administrator cannot be rewritten as the daily reading persona",
                )
            existing.display_name = DAILY_READING_USERNAME
            existing.bio = DAILY_READING_BIO
            existing.avatar_url = DAILY_READING_AVATAR_URL
            existing.status = "active"
            existing.role = "user"
            existing.is_persona = True
            await self.session.flush()
            return existing

        user = User(
            username=DAILY_READING_USERNAME,
            email=DAILY_READING_EMAIL,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            display_name=DAILY_READING_USERNAME,
            bio=DAILY_READING_BIO,
            avatar_url=DAILY_READING_AVATAR_URL,
            role="user",
            status="active",
            is_persona=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def _matching_untracked_topic(
        self,
        plan: DailyReadingPlan,
        board: Board,
        author: User,
    ) -> Topic | None:
        """Recover a same-author topic left between topic and audit commits.

        Key parameters are the stable plan, reading board, and persona. Return
        value is an exact same-title topic from the planned Shanghai date, or
        none. Side effect: database reads only.
        """

        candidates = list(
            await self.session.scalars(
                select(Topic).where(
                    Topic.board_id == board.id,
                    Topic.user_id == author.id,
                    Topic.title == plan.title,
                    Topic.deleted_at.is_(None),
                    Topic.id.in_(
                        select(Post.topic_id).where(
                            Post.post_number == 1,
                            Post.raw_md == plan.raw_md,
                        )
                    ),
                )
            )
        )
        for topic in candidates:
            created_at = topic.created_at
            if (
                created_at is not None
                and as_utc_datetime(created_at).astimezone(SHANGHAI_TZ).date()
                == plan.planned_date
            ):
                return topic
        return None

    async def _record_publish_audit(
        self,
        plan: DailyReadingPlan,
        topic: Topic,
        board: Board,
        author: User,
    ) -> None:
        """Commit one slot's idempotency and content-provenance audit record."""

        self.session.add(
            AuditLog(
                actor_id=author.id,
                action=DAILY_READING_AUDIT_ACTION,
                target_type=DAILY_READING_AUDIT_TARGET,
                target_id=plan.seed_key,
                board_id=board.id,
                data={
                    "seed_key": plan.seed_key,
                    "topic_id": topic.id,
                    "planned_date": plan.planned_date.isoformat(),
                    "slot": plan.slot,
                    "title": plan.title,
                    "author": DAILY_READING_USERNAME,
                    "board_slug": DAILY_READING_BOARD_SLUG,
                    "tags": list(plan.tags),
                    "model_name": plan.model_name,
                    "provider_mode": plan.provider_mode,
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()

    def _plan_from_draft(
        self,
        planned_date: date,
        slot: int,
        draft: DailyReadingDraft,
        *,
        model_name: str,
        provider_mode: str,
    ) -> DailyReadingPlan:
        """Attach stable date/slot and provider metadata to one validated draft."""

        return DailyReadingPlan(
            seed_key=daily_reading_seed_key(planned_date, slot),
            planned_date=planned_date,
            slot=slot,
            title=draft.title,
            raw_md=draft.raw_md,
            tags=draft.tags,
            model_name=model_name,
            provider_mode=provider_mode,
        )


def daily_reading_seed_key(planned_date: date, slot: int) -> str:
    """Return the stable audit idempotency key for one local date and slot."""

    if slot not in range(1, DAILY_READING_TOPIC_COUNT + 1):
        raise ValueError("daily reading slot must be 1 or 2")
    return f"daily-reading:{planned_date.isoformat()}:{slot:02d}"


def normalize_daily_reading_slots(slots: Sequence[int] | None) -> tuple[int, ...]:
    """Return validated, de-duplicated daily reading slots in publication order.

    Key parameter ``slots`` is optional and defaults to both slots. The returned
    tuple contains only 1 and/or 2; this pure validation helper has no side effects.
    """

    selected = tuple(dict.fromkeys(slots or range(1, DAILY_READING_TOPIC_COUNT + 1)))
    if not selected or any(
        slot not in range(1, DAILY_READING_TOPIC_COUNT + 1) for slot in selected
    ):
        raise ValueError("daily reading slots must contain only 1 or 2")
    return tuple(sorted(selected))


def local_today() -> date:
    """Return the current Asia/Shanghai date for daily reading publication."""

    return datetime.now(SHANGHAI_TZ).date()
