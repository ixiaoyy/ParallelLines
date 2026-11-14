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
    DAILY_READING_SCHEDULED_TIMES,
    DailyReadingDraft,
    generate_daily_reading_with_fallback,
    parse_daily_reading_drafts,
    validate_scheduled_reading_time,
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
DAILY_READING_AUTOMATION_MARKER = (
    "> 本帖由专用账号页边有光自动生成，使用创作角色口吻，不代表真人阅读经历。"
)


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
    scheduled_time: str | None = None

    def to_preview(self) -> dict[str, object]:
        """Return a JSON-safe full preview for CLI and background-job results."""

        preview = {
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
        if self.scheduled_time is not None:
            preview["scheduled_time"] = self.scheduled_time
        return preview


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
        scheduled_time: str | None = None,
    ) -> list[DailyReadingPlan]:
        """生成旧日更两篇或指定时段一篇计划；只读有界历史，可能调用一次模型。"""

        target_date = planned_date or local_today()
        validate_scheduled_reading_time(scheduled_time)
        recent_titles = await self._recent_titles()
        generation_options = {}
        if scheduled_time is not None:
            generation_options = {
                "scheduled_time": scheduled_time,
                "recent_bodies": await self._planned_day_bodies(target_date),
            }
        generated = await generate_daily_reading_with_fallback(
            self.settings,
            target_date,
            recent_titles,
            force_local=force_local,
            **generation_options,
        )
        return [
            self._plan_from_draft(
                target_date,
                slot,
                draft,
                model_name=generated.model_name,
                provider_mode=generated.provider_mode,
                scheduled_time=scheduled_time,
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
        scheduled_time: str | None = None,
    ) -> dict[str, object]:
        """预览或发布读书稿；旧slots保留两篇，新scheduled_time每时段一篇。

        参数为真实北京时间日期、模式及二选一的档期；返回计划和结果。
        auto模式只发布缺失稿，新档期只使用既有人设并按日期/时段幂等。
        """

        target_date = planned_date or local_today()
        validate_scheduled_reading_time(scheduled_time)
        if scheduled_time is not None and slots is not None:
            raise ValueError("scheduled_time cannot be combined with legacy daily reading slots")
        selected_slots = (
            (1,) if scheduled_time is not None else normalize_daily_reading_slots(slots)
        )
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
        # 新三时段与旧日更分开记账，重试只复用同一真实日期/时段的内容。
        if scheduled_time is not None:
            existing_result = await self._existing_result(
                daily_reading_seed_key(target_date, 1, scheduled_time=scheduled_time),
                fallback_slot=1,
            )
            existing = [existing_result] if existing_result is not None else []
        else:
            existing = await self._existing_day_results(target_date)
        existing_by_slot = {result.slot: result for result in existing}
        if (
            not dry_run
            and mode == "auto"
            and all(slot in existing_by_slot for slot in selected_slots)
        ):
            return {
                "dry_run": False,
                "publish_mode": mode,
                "planned_date": target_date.isoformat(),
                "plans": [],
                "results": [existing_by_slot[slot].to_dict() for slot in selected_slots],
            }

        effective_dry_run = dry_run or mode != "auto"
        plan_options = {"scheduled_time": scheduled_time} if scheduled_time is not None else {}
        plans = (
            await self.plan_day(target_date, force_local=force_local, **plan_options)
            if effective_dry_run
            else await self._stored_or_new_plans(
                target_date, force_local=force_local, **plan_options
            )
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
        scheduled_time: str | None = None,
    ) -> list[DailyReadingPlan]:
        """读取当天/时段已选稿或生成并提交一次；写入计划后重试不重新选稿。"""

        stored = await self._stored_plans(planned_date, scheduled_time=scheduled_time)
        if stored is not None:
            return stored
        plans = await self.plan_day(
            planned_date, force_local=force_local, scheduled_time=scheduled_time
        )
        first = plans[0]
        self.session.add(
            AuditLog(
                actor_id=None,
                action=DAILY_READING_PLAN_ACTION,
                target_type=DAILY_READING_PLAN_TARGET,
                target_id=daily_reading_plan_key(planned_date, scheduled_time=scheduled_time),
                board_id=None,
                data={
                    "planned_date": planned_date.isoformat(),
                    "model_name": first.model_name,
                    "provider_mode": first.provider_mode,
                    **({"scheduled_time": scheduled_time} if scheduled_time is not None else {}),
                    "posts": [
                        {
                            "title": plan.title,
                            "raw_md": (
                                plan.raw_md.removesuffix(f"\n\n{DAILY_READING_AUTOMATION_MARKER}")
                                if scheduled_time is not None
                                else plan.raw_md
                            ),
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

    async def _stored_plans(
        self,
        planned_date: date,
        *,
        scheduled_time: str | None = None,
    ) -> list[DailyReadingPlan] | None:
        """读取真实日期/时段的一份已提交计划；坏数据失败，不偷偷替换已选稿。"""

        audit = await self.session.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == DAILY_READING_PLAN_ACTION,
                AuditLog.target_type == DAILY_READING_PLAN_TARGET,
                AuditLog.target_id
                == daily_reading_plan_key(planned_date, scheduled_time=scheduled_time),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if audit is None:
            return None
        data = audit.data or {}
        drafts = parse_daily_reading_drafts(
            {"posts": data.get("posts")},
            expected_count=1 if scheduled_time is not None else 2,
        )
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
                scheduled_time=scheduled_time,
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
            author = (
                await self._require_scheduled_persona()
                if plan.scheduled_time is not None
                else await self._ensure_persona()
            )
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
                int(slot) if isinstance(slot, int | str) and str(slot).isdigit() else fallback_slot
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

    async def _planned_day_bodies(self, planned_date: date) -> list[str]:
        """读取当日已选稿正文供三时段去重；至多四份计划，不读帖子或私人内容。"""

        if self.session is None:
            return []
        plan_keys = [daily_reading_plan_key(planned_date)] + [
            daily_reading_plan_key(planned_date, scheduled_time=value)
            for value in DAILY_READING_SCHEDULED_TIMES
        ]
        audits = list(
            await self.session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.action == DAILY_READING_PLAN_ACTION,
                    AuditLog.target_type == DAILY_READING_PLAN_TARGET,
                    AuditLog.target_id.in_(plan_keys),
                )
                .order_by(AuditLog.created_at.desc())
                .limit(4)
            )
        )
        return [
            body
            for audit in audits
            for post in (audit.data or {}).get("posts", [])
            if isinstance(post, dict) and isinstance(body := post.get("raw_md"), str)
        ]

    async def _require_scheduled_persona(self) -> User:
        """新定时发布只使用既有专用人设；缺失、身份冲突或禁用时失败，不创建/改写账号。"""

        user = await self.session.scalar(
            select(User).where(
                User.username == DAILY_READING_USERNAME,
                User.email == DAILY_READING_EMAIL,
            )
        )
        if (
            user is None
            or user.username != DAILY_READING_USERNAME
            or user.email != DAILY_READING_EMAIL
            or user.role != "user"
            or user.status != "active"
            or user.is_persona is not True
        ):
            raise ValidationError(
                "daily_reading_scheduled_persona_unavailable",
                "读书定时发布的专用身份不存在或不可用",
                {"username": DAILY_READING_USERNAME},
            )
        return user

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
            if existing.username != DAILY_READING_USERNAME or existing.email != DAILY_READING_EMAIL:
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
                    *([Topic.deleted_at.is_(None)] if plan.scheduled_time is None else []),
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
                and as_utc_datetime(created_at).astimezone(SHANGHAI_TZ).date() == plan.planned_date
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
                    **(
                        {"scheduled_time": plan.scheduled_time}
                        if plan.scheduled_time is not None
                        else {}
                    ),
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
        scheduled_time: str | None = None,
    ) -> DailyReadingPlan:
        """Attach stable date/slot and provider metadata to one validated draft."""

        raw_md = draft.raw_md
        if scheduled_time is not None:
            if not raw_md.endswith(DAILY_READING_AUTOMATION_MARKER):
                raw_md = f"{raw_md}\n\n{DAILY_READING_AUTOMATION_MARKER}"
        return DailyReadingPlan(
            seed_key=daily_reading_seed_key(planned_date, slot, scheduled_time=scheduled_time),
            planned_date=planned_date,
            slot=slot,
            title=draft.title,
            raw_md=raw_md,
            tags=draft.tags,
            model_name=model_name,
            provider_mode=provider_mode,
            scheduled_time=scheduled_time,
        )


def daily_reading_seed_key(
    planned_date: date, slot: int, *, scheduled_time: str | None = None
) -> str:
    """Return the stable audit idempotency key for one local date and slot."""

    validate_scheduled_reading_time(scheduled_time)
    if scheduled_time is not None:
        if slot != 1:
            raise ValueError("scheduled reading publishes one topic per time slot")
        return f"daily-reading:{planned_date.isoformat()}:{scheduled_time.replace(':', '')}:01"
    if slot not in range(1, DAILY_READING_TOPIC_COUNT + 1):
        raise ValueError("daily reading slot must be 1 or 2")
    return f"daily-reading:{planned_date.isoformat()}:{slot:02d}"


def daily_reading_plan_key(planned_date: date, *, scheduled_time: str | None = None) -> str:
    """返回旧日更或三时段选稿标识；保留真实日期且不与旧计划混用，无副作用。"""

    validate_scheduled_reading_time(scheduled_time)
    suffix = f":{scheduled_time.replace(':', '')}" if scheduled_time is not None else ""
    return f"{planned_date.isoformat()}{suffix}"


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
