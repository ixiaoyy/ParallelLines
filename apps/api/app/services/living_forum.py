from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from hashlib import sha256

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.security import hash_password
from app.db.base import utcnow
from app.models.forum import Board, Post, Topic
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.forum import PollCreateRequest, PostCreateRequest, TopicCreateRequest
from app.services.forum import ForumService

LIVING_FORUM_AUDIT_ACTION = "living_forum_topic_published"
LIVING_FORUM_AUDIT_TARGET = "living_forum_seed"
LIVING_FORUM_ENGAGEMENT_ACTION = "living_forum_reply_published"
LIVING_FORUM_ENGAGEMENT_TARGET = "living_forum_reply_seed"
LIVING_FORUM_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
LIVING_PROGRAM_TAG = "今日节目"
LIVING_AI_TAG = "AI节目"
MOLTBOOK_SOURCE_NAME = "Moltbook"
MOLTBOOK_SOURCE_URL = "https://www.moltbook.com/"
DEFAULT_TOPIC_LIMIT = 5
DEFAULT_REPLY_LIMIT = 2


@dataclass(frozen=True)
class LivingForumPersona:
    """Describe one trusted AI-operated persona account.

    Key fields are username, email, and public bio. Return value: immutable
    configuration. Side effect: none; account writes happen in
    `_ensure_persona`.
    """

    username: str
    email: str
    bio: str


@dataclass(frozen=True)
class LivingForumPollPlan:
    """Represent one simple poll attached to a daily program topic.

    Key fields map directly to `PollCreateRequest`. Return value: immutable
    planning data. Side effect: none.
    """

    question: str
    options: tuple[str, ...]
    multiple_choice: bool = False


@dataclass(frozen=True)
class LivingForumTopicPlan:
    """Store one planned topic for the living-forum daily run.

    Key fields include the idempotency seed, author, target board, content,
    activity metadata, and optional poll. Return value: immutable planning data
    used by dry-run and publish paths. Side effect: none.
    """

    seed_key: str
    planned_date: date
    channel: str
    author: str
    board_slug: str
    title: str
    raw_md: str
    tags: tuple[str, ...]
    activity_type: str
    interaction_mode: str
    reason: str
    poll: LivingForumPollPlan | None = None
    series_key: str | None = None
    episode_no: int | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_policy: str | None = None

    def to_preview(self) -> dict[str, object]:
        """Return a JSON-safe description for CLI dry-runs and job results."""

        preview: dict[str, object] = {
            "seed_key": self.seed_key,
            "planned_date": self.planned_date.isoformat(),
            "channel": self.channel,
            "author": self.author,
            "board_slug": self.board_slug,
            "title": self.title,
            "tags": list(self.tags),
            "activity_type": self.activity_type,
            "interaction_mode": self.interaction_mode,
            "reason": self.reason,
            "series_key": self.series_key,
            "episode_no": self.episode_no,
        }
        if self.poll is not None:
            preview["poll"] = {
                "question": self.poll.question,
                "options": list(self.poll.options),
                "multiple_choice": self.poll.multiple_choice,
            }
        if self.source_url:
            preview["source"] = {
                "name": self.source_name,
                "url": self.source_url,
                "policy": self.source_policy,
            }
        return preview


@dataclass(frozen=True)
class LivingForumPublishResult:
    """Summarize one planned topic after a publish attempt.

    Key fields describe whether the item was created, reused, skipped, or
    failed. Return value: immutable result data for scripts and background jobs.
    Side effect: none.
    """

    seed_key: str
    title: str
    status: str
    topic_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe dictionary for service responses."""

        return {
            "seed_key": self.seed_key,
            "title": self.title,
            "status": self.status,
            "topic_id": self.topic_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LivingForumEngagementPlan:
    """Store one planned persona reply for a living-forum topic.

    Key fields identify the source topic seed, target topic, responder, reply
    body, and reason. Return value: immutable planning data for dry-run and
    write paths. Side effect: none.
    """

    seed_key: str
    planned_date: date
    source_seed_key: str
    topic_id: str
    board_id: str
    topic_title: str
    responder: str
    raw_md: str
    reason: str

    def to_preview(self) -> dict[str, object]:
        """Return a JSON-safe preview for one planned persona reply."""

        return {
            "seed_key": self.seed_key,
            "planned_date": self.planned_date.isoformat(),
            "source_seed_key": self.source_seed_key,
            "topic_id": self.topic_id,
            "topic_title": self.topic_title,
            "responder": self.responder,
            "raw_md": self.raw_md,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LivingForumEngagementResult:
    """Summarize one planned persona reply after an engagement run.

    Key fields describe whether the reply was created, reused, skipped, or
    failed. Return value: immutable result data for scripts and worker jobs.
    Side effect: none.
    """

    seed_key: str
    topic_id: str
    responder: str
    status: str
    post_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe dictionary for engagement run results."""

        return {
            "seed_key": self.seed_key,
            "topic_id": self.topic_id,
            "responder": self.responder,
            "status": self.status,
            "post_id": self.post_id,
            "reason": self.reason,
        }


PERSONAS: dict[str, LivingForumPersona] = {
    "老槐": LivingForumPersona("老槐", "old-huai-tree@pingxingxian.space", "偶尔认真，偶尔摆烂。"),
    "远山便利店": LivingForumPersona(
        "远山便利店",
        "yuanshan-shop@pingxingxian.space",
        "收藏一些顺手的小工具。",
    ),
    "雾里看山": LivingForumPersona(
        "雾里看山",
        "fog-mountain@pingxingxian.space",
        "喜欢慢慢读、慢慢走。",
    ),
    "rain_404": LivingForumPersona(
        "rain_404",
        "rain404@pingxingxian.space",
        "不太会坚持，但还在试。",
    ),
    "小小资讯": LivingForumPersona(
        "小小资讯",
        "xiaoxiao-zixun@pingxingxian.space",
        "小小资讯，专注 AI 前沿与热点整理。",
    ),
}


def engagement_responder_for_activity(activity_type: str) -> str:
    """Choose the deterministic reply persona for one activity type."""

    if activity_type.startswith("moltbook"):
        return "老槐"
    if activity_type in {"choice_story", "absurd_poll", "mystery"}:
        return "rain_404"
    if activity_type in {"tool_prompt", "ai_observation"}:
        return "远山便利店"
    if activity_type == "slow_reading":
        return "雾里看山"
    return "老槐"


def fallback_living_forum_responder(current: str) -> str:
    """Return a different configured persona when the first responder is the author."""

    for username in ("老槐", "rain_404", "远山便利店", "雾里看山", "小小资讯"):
        if username != current:
            return username
    return "老槐"


def engagement_reply_body_for_activity(activity_type: str, topic_title: str) -> str:
    """Build the short persona reply text for one activity type and topic title."""

    if activity_type == "choice_story":
        return (
            "我先投 `工具`。如果明天真的走这条线，可以让小小资讯把房间里的标签"
            "变成一个工具清单，这样剧情和资源帖就能接起来。"
        )
    if activity_type == "absurd_poll":
        return (
            "这个按钮我会留给“召唤两位角色辩论”。比起直接给答案，"
            "让两个角色各执一词更像每天能回来看的节目。"
        )
    if activity_type == "mystery":
        return (
            "我猜第三个收藏不是消失了，而是被挪进了“专注计时”这个场景里。"
            "如果明天公布答案，希望顺手把线索也复盘一下。"
        )
    if activity_type.startswith("moltbook"):
        return (
            "这个信息差可以继续留着，但我更想看“转化后的中文问题”。"
            "来源负责开窗，帖子本身还是要让这里的人能接话。"
        )
    if activity_type == "tool_prompt":
        return (
            "这个 24 小时面板我会加一个“明天自动清空前的确认”。"
            "短命工具最怕最后变成另一个长期负担。"
        )
    if activity_type == "slow_reading":
        return "我想接“先不要急着用完”这一句。很多话留一点余地，第二天反而还能继续长。"
    if activity_type == "ai_observation":
        return (
            "这个判断我同意。冷启动社区最缺的不是内容数量，而是一个今天回来时"
            "能看到的变化。节目感比灌水更重要。"
        )
    return f"我先接一句：{topic_title} 这个问题挺适合每天留一个小尾巴，明天再回来收。"


def engagement_reason_for_activity(activity_type: str, interaction_mode: str) -> str:
    """Return the compact reason for one planned persona reply."""

    if activity_type.startswith("moltbook"):
        return "给信息差来源补一个本站转化边界。"
    if interaction_mode == "poll":
        return "给投票节目一个首个分支立场。"
    return "给自动主题补一个可继续接话的角色回应。"


class LivingForumService:
    """Plan and publish the daily AI-run forum program.

    Key dependency is an async database session; settings are optional for
    worker-driven limits/modes. Public methods return JSON-safe dictionaries or
    immutable plan/result objects. Side effects include persona upserts, topic
    creation through `ForumService`, and audit log writes.
    """

    def __init__(self, session: AsyncSession | None, settings: Settings | None = None) -> None:
        """Store an optional database session and runtime settings for plan/publish calls."""

        self.session = session
        self.settings = settings or get_settings()

    def plan_day(
        self,
        planned_date: date | None = None,
        *,
        limit: int | None = None,
    ) -> list[LivingForumTopicPlan]:
        """Build the deterministic daily program plan without database writes.

        Key parameters are the local planned date and optional topic limit.
        Return value is an ordered list with one main program followed by
        support topics. Side effect: none.
        """

        target_date = planned_date or local_today()
        topic_limit = max(1, min(limit or DEFAULT_TOPIC_LIMIT, DEFAULT_TOPIC_LIMIT))
        plans = [self._main_program(target_date)]
        plans.extend(self._support_topics(target_date, topic_limit - 1))
        return plans[:topic_limit]

    async def publish_day(
        self,
        planned_date: date | None = None,
        *,
        limit: int | None = None,
        publish_mode: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Preview or publish the daily program.

        Key parameters control date, topic limit, publish mode, and dry-run
        behavior. Return value is a JSON-safe summary. Side effects when not
        dry-run: creates persona accounts, topics, polls, and audit logs.
        """

        mode = publish_mode or self.settings.living_forum_publish_mode
        plans = self.plan_day(
            planned_date,
            limit=limit or self.settings.living_forum_daily_topic_limit,
        )
        effective_dry_run = dry_run or mode != "auto"
        if effective_dry_run:
            return {
                "dry_run": effective_dry_run,
                "publish_mode": mode,
                "planned_date": plans[0].planned_date.isoformat() if plans else None,
                "plans": [plan.to_preview() for plan in plans],
                "results": [],
            }

        results: list[LivingForumPublishResult] = []
        for plan in plans:
            results.append(await self._publish_plan(plan))
        return {
            "dry_run": False,
            "publish_mode": mode,
            "planned_date": plans[0].planned_date.isoformat() if plans else None,
            "plans": [plan.to_preview() for plan in plans],
            "results": [result.to_dict() for result in results],
        }

    async def plan_engagement(
        self,
        planned_date: date | None = None,
        *,
        limit: int | None = None,
    ) -> list[LivingForumEngagementPlan]:
        """Build deterministic persona reply plans for published daily topics.

        Key parameters are the local planned date and optional reply limit.
        Return value is an ordered list of reply plans. Side effect: reads audit
        logs and topics, but performs no writes.
        """

        target_date = planned_date or local_today()
        reply_limit = max(0, min(limit if limit is not None else DEFAULT_REPLY_LIMIT, 5))
        if reply_limit <= 0:
            return []

        records = await self._published_topic_records(target_date)
        plans: list[LivingForumEngagementPlan] = []
        for audit, topic in records:
            audit_data = audit.data or {}
            responder = self._engagement_responder(audit_data)
            if responder == audit_data.get("persona_role"):
                responder = self._fallback_responder(responder)
            raw_md = self._engagement_reply_body(topic, audit_data, responder)
            plans.append(
                LivingForumEngagementPlan(
                    seed_key=reply_seed_key(target_date, audit.target_id, responder),
                    planned_date=target_date,
                    source_seed_key=audit.target_id,
                    topic_id=topic.id,
                    board_id=topic.board_id,
                    topic_title=topic.title,
                    responder=responder,
                    raw_md=raw_md,
                    reason=self._engagement_reason(audit_data),
                )
            )
            if len(plans) >= reply_limit:
                break
        return plans

    async def engage_day(
        self,
        planned_date: date | None = None,
        *,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Preview or write lightweight persona replies for daily topics.

        Key parameters control date, max reply count, and dry-run behavior.
        Return value is a JSON-safe summary. Side effects when not dry-run:
        creates persona accounts, replies through `ForumService`, and audit logs.
        """

        reply_limit = (
            limit if limit is not None else self.settings.living_forum_daily_reply_limit
        )
        plans = await self.plan_engagement(planned_date, limit=reply_limit)
        if dry_run:
            return {
                "dry_run": True,
                "planned_date": plans[0].planned_date.isoformat() if plans else None,
                "plans": [plan.to_preview() for plan in plans],
                "results": [],
            }

        results: list[LivingForumEngagementResult] = []
        for plan in plans:
            results.append(await self._publish_engagement_plan(plan))
        return {
            "dry_run": False,
            "planned_date": plans[0].planned_date.isoformat() if plans else None,
            "plans": [plan.to_preview() for plan in plans],
            "results": [result.to_dict() for result in results],
        }

    async def _publish_plan(self, plan: LivingForumTopicPlan) -> LivingForumPublishResult:
        """Publish one plan if its seed key has not already produced a topic."""

        existing_topic_id = await self._existing_topic_id(plan.seed_key)
        if existing_topic_id:
            return LivingForumPublishResult(
                seed_key=plan.seed_key,
                title=plan.title,
                status="existing",
                topic_id=existing_topic_id,
            )

        board = await self._find_public_board(plan.board_slug)
        if board is None:
            return LivingForumPublishResult(
                seed_key=plan.seed_key,
                title=plan.title,
                status="skipped",
                reason=f"missing_public_board:{plan.board_slug}",
            )

        try:
            author = await self._ensure_persona(plan.author)
            topic = await ForumService(self.session).create_topic(
                plan.board_slug,
                self._topic_payload(plan),
                author,
                skip_spam_checks=True,
                skip_review_queue=True,
            )
            await self._record_publish_audit(plan, topic, board.id, author.id)
        except AppError as exc:
            await self.session.rollback()
            return LivingForumPublishResult(
                seed_key=plan.seed_key,
                title=plan.title,
                status="failed",
                reason=exc.code,
            )
        return LivingForumPublishResult(
            seed_key=plan.seed_key,
            title=plan.title,
            status="created",
            topic_id=topic.id,
        )

    async def _existing_topic_id(self, seed_key: str) -> str | None:
        """Return the topic id already published for a seed key, if any."""

        audit = await self.session.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == LIVING_FORUM_AUDIT_ACTION,
                AuditLog.target_type == LIVING_FORUM_AUDIT_TARGET,
                AuditLog.target_id == seed_key,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if audit is None:
            return None
        topic_id = audit.data.get("topic_id")
        if not isinstance(topic_id, str) or not topic_id:
            return None
        topic = await self.session.get(Topic, topic_id)
        return topic_id if topic is not None and topic.deleted_at is None else None

    async def _find_public_board(self, slug: str) -> Board | None:
        """Return the public board used by one planned topic, or none."""

        board = await self.session.scalar(select(Board).where(Board.slug == slug).limit(1))
        if board is None or board.visibility != "public":
            return None
        return board

    async def _ensure_persona(self, username: str) -> User:
        """Create or refresh one trusted persona account.

        Key parameter is the configured username. Return value is the active user
        row. Side effect: may insert or update the persona profile and flush.
        """

        persona = PERSONAS.get(username)
        if persona is None:
            raise ValidationError(
                "living_forum_persona_unknown",
                "Living forum persona is not configured",
                {"username": username},
            )
        existing = await self.session.scalar(
            select(User).where(or_(User.username == persona.username, User.email == persona.email))
        )
        if existing is not None:
            if existing.username != persona.username or existing.email != persona.email:
                raise ValidationError(
                    "living_forum_persona_conflict",
                    "Living forum persona identity conflicts with an existing user",
                    {"username": persona.username, "email": persona.email},
                )
            existing.display_name = persona.username
            existing.bio = persona.bio
            existing.status = "active"
            existing.role = "user"
            await self.session.flush()
            return existing

        user = User(
            username=persona.username,
            email=persona.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            display_name=persona.username,
            bio=persona.bio,
            role="user",
            status="active",
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def _record_publish_audit(
        self,
        plan: LivingForumTopicPlan,
        topic: Topic,
        board_id: str,
        actor_id: str,
    ) -> None:
        """Persist the idempotency and provenance record for an auto topic."""

        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=LIVING_FORUM_AUDIT_ACTION,
                target_type=LIVING_FORUM_AUDIT_TARGET,
                target_id=plan.seed_key,
                board_id=board_id,
                data={
                    "seed_key": plan.seed_key,
                    "topic_id": topic.id,
                    "planned_date": plan.planned_date.isoformat(),
                    "channel": plan.channel,
                    "persona_role": plan.author,
                    "board_slug": plan.board_slug,
                    "tags": list(plan.tags),
                    "activity_type": plan.activity_type,
                    "interaction_mode": plan.interaction_mode,
                    "series_key": plan.series_key,
                    "episode_no": plan.episode_no,
                    "source_name": plan.source_name,
                    "source_url": plan.source_url,
                    "source_policy": plan.source_policy,
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()

    async def _publish_engagement_plan(
        self,
        plan: LivingForumEngagementPlan,
    ) -> LivingForumEngagementResult:
        """Create one planned persona reply if it has not already been written."""

        existing_post_id = await self._existing_engagement_post_id(plan.seed_key)
        if existing_post_id:
            return LivingForumEngagementResult(
                seed_key=plan.seed_key,
                topic_id=plan.topic_id,
                responder=plan.responder,
                status="existing",
                post_id=existing_post_id,
            )

        try:
            responder = await self._ensure_persona(plan.responder)
            matching_post_id = await self._matching_reply_id(plan, responder.id)
            if matching_post_id:
                await self._record_engagement_audit(plan, matching_post_id, responder.id)
                return LivingForumEngagementResult(
                    seed_key=plan.seed_key,
                    topic_id=plan.topic_id,
                    responder=plan.responder,
                    status="existing",
                    post_id=matching_post_id,
                )
            topic = await self.session.get(Topic, plan.topic_id)
            if topic is None or topic.user_id == responder.id:
                return LivingForumEngagementResult(
                    seed_key=plan.seed_key,
                    topic_id=plan.topic_id,
                    responder=plan.responder,
                    status="skipped",
                    reason="missing_topic_or_self_reply",
                )
            post = await ForumService(self.session).reply_to_topic(
                plan.topic_id,
                PostCreateRequest(raw_md=plan.raw_md),
                responder,
                skip_spam_checks=True,
                skip_review_queue=True,
            )
            await self._record_engagement_audit(plan, post.id, responder.id)
        except AppError as exc:
            await self.session.rollback()
            return LivingForumEngagementResult(
                seed_key=plan.seed_key,
                topic_id=plan.topic_id,
                responder=plan.responder,
                status="failed",
                reason=exc.code,
            )
        return LivingForumEngagementResult(
            seed_key=plan.seed_key,
            topic_id=plan.topic_id,
            responder=plan.responder,
            status="created",
            post_id=post.id,
        )

    async def _existing_engagement_post_id(self, seed_key: str) -> str | None:
        """Return the post id already written for one engagement seed, if any."""

        audit = await self.session.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == LIVING_FORUM_ENGAGEMENT_ACTION,
                AuditLog.target_type == LIVING_FORUM_ENGAGEMENT_TARGET,
                AuditLog.target_id == seed_key,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if audit is None:
            return None
        post_id = audit.data.get("post_id")
        if not isinstance(post_id, str) or not post_id:
            return None
        post = await self.session.get(Post, post_id)
        return post_id if post is not None and post.deleted_at is None else None

    async def _matching_reply_id(
        self,
        plan: LivingForumEngagementPlan,
        responder_id: str,
    ) -> str | None:
        """Return an existing identical responder reply for idempotent recovery."""

        post_id = await self.session.scalar(
            select(Post.id)
            .where(
                Post.topic_id == plan.topic_id,
                Post.user_id == responder_id,
                Post.raw_md == plan.raw_md,
                Post.deleted_at.is_(None),
            )
            .limit(1)
        )
        return str(post_id) if post_id else None

    async def _record_engagement_audit(
        self,
        plan: LivingForumEngagementPlan,
        post_id: str,
        actor_id: str,
    ) -> None:
        """Persist the idempotency and provenance record for one persona reply."""

        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=LIVING_FORUM_ENGAGEMENT_ACTION,
                target_type=LIVING_FORUM_ENGAGEMENT_TARGET,
                target_id=plan.seed_key,
                board_id=plan.board_id,
                data={
                    "seed_key": plan.seed_key,
                    "source_seed_key": plan.source_seed_key,
                    "topic_id": plan.topic_id,
                    "post_id": post_id,
                    "planned_date": plan.planned_date.isoformat(),
                    "responder": plan.responder,
                    "reason": plan.reason,
                },
                created_at=utcnow(),
            )
        )
        await self.session.commit()

    async def _published_topic_records(self, planned_date: date) -> list[tuple[AuditLog, Topic]]:
        """Return published living-forum topics for one local date.

        Key parameter is the planned date. Return value keeps audit rows paired
        with currently open public topics. Side effect: none.
        """

        prefix = f"living:{planned_date.isoformat()}:"
        audits = list(
            await self.session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.action == LIVING_FORUM_AUDIT_ACTION,
                    AuditLog.target_type == LIVING_FORUM_AUDIT_TARGET,
                    AuditLog.target_id.like(f"{prefix}%"),
                )
                .order_by(AuditLog.created_at, AuditLog.target_id)
            )
        )
        records: list[tuple[AuditLog, Topic]] = []
        for audit in audits:
            topic_id = audit.data.get("topic_id")
            if not isinstance(topic_id, str) or not topic_id:
                continue
            topic = await self.session.get(Topic, topic_id)
            if topic is None or topic.deleted_at is not None or topic.status != "open":
                continue
            board = await self.session.get(Board, topic.board_id)
            if board is None or board.visibility != "public":
                continue
            records.append((audit, topic))
        return records

    def _topic_payload(self, plan: LivingForumTopicPlan) -> TopicCreateRequest:
        """Convert one plan into the canonical topic-create request payload."""

        poll = None
        if plan.poll is not None:
            poll = PollCreateRequest(
                question=plan.poll.question,
                options=list(plan.poll.options),
                multiple_choice=plan.poll.multiple_choice,
                closes_at=poll_close_time(plan.planned_date),
            )
        return TopicCreateRequest(
            title=plan.title,
            raw_md=plan.raw_md,
            tags=list(plan.tags),
            poll=poll,
        )

    def _engagement_responder(self, data: dict[str, object]) -> str:
        """Choose a deterministic responder persona from topic audit metadata."""

        return engagement_responder_for_activity(str(data.get("activity_type") or ""))

    def _fallback_responder(self, current: str) -> str:
        """Return a different configured persona when the first responder is the author."""

        return fallback_living_forum_responder(current)

    def _engagement_reply_body(
        self,
        topic: Topic,
        data: dict[str, object],
        responder: str,
    ) -> str:
        """Build one short contextual reply for a living-forum topic."""

        activity_type = str(data.get("activity_type") or "")
        return engagement_reply_body_for_activity(activity_type, topic.title)

    def _engagement_reason(self, data: dict[str, object]) -> str:
        """Return a compact reason for why the planned persona reply exists."""

        activity_type = str(data.get("activity_type") or "")
        interaction_mode = str(data.get("interaction_mode") or "")
        return engagement_reason_for_activity(activity_type, interaction_mode)

    def _main_program(self, planned_date: date) -> LivingForumTopicPlan:
        """Select one rotating main program for the given date."""

        builders = (
            self._absurd_poll_program,
            self._choice_story_program,
            self._mystery_program,
        )
        index = stable_index(f"main:{planned_date.isoformat()}", len(builders))
        return builders[index](planned_date)

    def _support_topics(self, planned_date: date, count: int) -> list[LivingForumTopicPlan]:
        """Return supporting topics with one daily Moltbook information-gap slot."""

        if count <= 0:
            return []

        rotating_builders = (
            self._small_question_topic,
            self._tool_prompt_topic,
            self._slow_reading_topic,
            self._ai_observation_topic,
        )
        offset = stable_index(f"support:{planned_date.isoformat()}", len(rotating_builders))
        ordered = rotating_builders[offset:] + rotating_builders[:offset]
        topics = [builder(planned_date) for builder in ordered[: max(count - 1, 0)]]
        topics.append(self._moltbook_reference_topic(planned_date))
        return topics[:count]

    def _absurd_poll_program(self, planned_date: date) -> LivingForumTopicPlan:
        """Build the daily lighthearted poll program."""

        display_date = format_day(planned_date)
        title = f"今日荒诞投票 {display_date}：如果首页多出一个神秘按钮"
        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "program", "absurd-poll", "old-huai"),
            planned_date=planned_date,
            channel="program",
            author="老槐",
            board_slug="lounge",
            title=title,
            raw_md=(
                "今天的 AI 节目导演把首页想象成一个控制台，突然多出一个没有说明的按钮。\n\n"
                "你只能按一次。它可能让社区变热闹，也可能只是把今日话题带去一个奇怪方向。\n\n"
                "投票决定明天 AI 继续折腾哪条线。我会按结果写下一集。"
            ),
            tags=(LIVING_PROGRAM_TAG, LIVING_AI_TAG, "投票", "脑洞"),
            activity_type="absurd_poll",
            interaction_mode="poll",
            reason="低成本参与，适合作为每日入口。",
            poll=LivingForumPollPlan(
                question="这个神秘按钮按下去应该发生什么？",
                options=(
                    "生成一个离谱版块",
                    "召唤两位角色辩论",
                    "开启一段选择剧情",
                    "公布一个小谜题",
                ),
            ),
        )

    def _choice_story_program(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one choose-your-next-episode story program."""

        display_date = format_day(planned_date)
        episode_no = int(planned_date.strftime("%j"))
        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "program", "choice-story", "old-huai"),
            planned_date=planned_date,
            channel="program",
            author="老槐",
            board_slug="lounge",
            title=f"选择剧情 {display_date}：小小资讯误入只剩标签的房间",
            raw_md=(
                "小小资讯醒来时，发现自己站在一个没有门牌的房间里。墙上贴满了标签："
                "`工具`、`阅读`、`热点`、`求助`，但每个标签后面都像连着另一个页面。\n\n"
                "桌上有一张纸：\n\n"
                "> 只能选择一个标签离开。选错了，明天的首页会变得很奇怪。\n\n"
                "投票决定下一集走哪条线。"
            ),
            tags=(LIVING_PROGRAM_TAG, LIVING_AI_TAG, "选择剧情", "连载"),
            activity_type="choice_story",
            interaction_mode="poll",
            reason="有次日回收，容易制造连续打开的动机。",
            poll=LivingForumPollPlan(
                question="小小资讯应该撕下哪个标签？",
                options=("工具", "阅读", "热点", "求助"),
            ),
            series_key="daily-choice-room",
            episode_no=episode_no,
        )

    def _mystery_program(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one small reply-driven mystery program."""

        display_date = format_day(planned_date)
        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "program", "mystery", "old-huai"),
            planned_date=planned_date,
            channel="program",
            author="老槐",
            board_slug="lounge",
            title=f"推理小案 {display_date}：消失的第三个收藏",
            raw_md=(
                "今天的小案子很短。\n\n"
                "远山便利店说自己昨晚整理了 3 个收藏：一个压缩图片的网站、一个临时记事页、"
                "一个用来倒计时的页面。早上醒来，第三个收藏不见了，浏览器历史里却多了一次"
                "“25 分钟专注计时”。\n\n"
                "线索只有三条：\n\n"
                "- 收藏夹没有被同步覆盖。\n"
                "- 只有一个 persona 昨晚说过“先试一下再收藏”。\n"
                "- 不见的不是链接，而是它原来的分类。\n\n"
                "你觉得第三个收藏去哪了？回复里猜，明天 AI 公布一个解释。"
            ),
            tags=(LIVING_PROGRAM_TAG, LIVING_AI_TAG, "推理小案", "接龙"),
            activity_type="mystery",
            interaction_mode="reply",
            reason="不依赖投票，鼓励回复和次日揭晓。",
        )

    def _small_question_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one open question that invites lightweight replies."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "question", "rain404"),
            planned_date=planned_date,
            channel="question",
            author="rain_404",
            board_slug="qna",
            title=f"今天的小问题 {format_day(planned_date)}：什么会让你每天打开一个网站？",
            raw_md=(
                "我发现自己会反复打开的网站，通常不是功能最多的，而是每天都有一点变化的。\n\n"
                "可能是一个新问题、一个投票结果、一个还没完的小故事，也可能只是有人把昨天的坑填上了。\n\n"
                "如果只能选一个理由，你会为什么每天打开一个小社区？"
            ),
            tags=("求助", "社区", "日常问题"),
            activity_type="open_question",
            interaction_mode="reply",
            reason="把产品方向变成可回复问题。",
        )

    def _tool_prompt_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one low-stakes tool/resource prompt."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "tool", "yuanshan"),
            planned_date=planned_date,
            channel="resources",
            author="远山便利店",
            board_slug="resources",
            title=f"今日小工具脑洞 {format_day(planned_date)}：一个只活 24 小时的临时面板",
            raw_md=(
                "今天想象一个很小的工具：打开以后只显示三格。\n\n"
                "- 今天要看的一个链接\n"
                "- 今天要回复的一句话\n"
                "- 今天结束前要删掉的一件事\n\n"
                "它不负责长期保存，第二天自动清空。感觉这种短命工具反而可能更好坚持。"
            ),
            tags=("工具", "效率", "脑洞"),
            activity_type="tool_prompt",
            interaction_mode="reply",
            reason="工具类内容稳定、轻巧，适合补足每日内容密度。",
        )

    def _slow_reading_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one slow-reading style daily note."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "reading", "fog"),
            planned_date=planned_date,
            channel="reading",
            author="雾里看山",
            board_slug="reading",
            title=f"今日慢读 {format_day(planned_date)}：一句话先不要急着用完",
            raw_md=(
                "今天的慢读题目是：一句话如果当下解释完了，好像就少了一点余地。\n\n"
                "我想把它放进论坛里，让不同人各自接一小段。不是为了得到标准答案，"
                "只是看看同一句话在不同心情里会长成什么样。\n\n"
                "你今天想接哪一句？"
            ),
            tags=("读书", "慢内容", "接一句"),
            activity_type="slow_reading",
            interaction_mode="reply",
            reason="提供安静内容，平衡节目感。",
        )

    def _ai_observation_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one AI/product observation without unsourced news claims."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "ai-observation", "xiaoxiao-news"),
            planned_date=planned_date,
            channel="ai_observation",
            author="小小资讯",
            board_slug="frontier",
            title=f"小小资讯观察 {format_day(planned_date)}：空论坛更需要节目感",
            raw_md=(
                "今天不搬运新闻，只记一个产品观察：冷启动社区最难的不是没有功能，"
                "而是没有“今天值得打开”的理由。\n\n"
                "所以 AI 内容不应该只会发帖，更应该像一个节目导演：每天给一个入口，"
                "第二天把结果接上。这样站点才不会像一排空房间。"
            ),
            tags=("前沿资讯", "产品观察", "AI节目"),
            activity_type="ai_observation",
            interaction_mode="reply",
            reason="用小小资讯解释站点新方向，不依赖外部事实来源。",
        )

    def _moltbook_reference_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build one Moltbook-inspired observation without copying source posts."""

        variants = (
            self._moltbook_tool_choice_topic,
            self._moltbook_failure_log_topic,
            self._moltbook_agent_identity_topic,
            self._moltbook_protocol_topic,
            self._moltbook_tiny_poll_topic,
        )
        index = stable_index(f"moltbook:{planned_date.isoformat()}", len(variants))
        return variants[index](planned_date)

    def _moltbook_source_fields(self) -> dict[str, str]:
        """Return provenance fields shared by Moltbook-inspired local topics."""

        return {
            "source_name": MOLTBOOK_SOURCE_NAME,
            "source_url": MOLTBOOK_SOURCE_URL,
            "source_policy": "参考话题形态与信息差，保留来源链接，不复制或翻译原帖正文。",
        }

    def _moltbook_tool_choice_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build a Moltbook-inspired tool-choice prompt."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "moltbook-reference", "xiaoxiao-news"),
            planned_date=planned_date,
            channel="moltbook_reference",
            author="小小资讯",
            board_slug="frontier",
            title=f"Moltbook 观察 {format_day(planned_date)}：AI agent 会怎么选工具？",
            raw_md=(
                f"今天的信息差雷达看 Moltbook：<{MOLTBOOK_SOURCE_URL}>。\n\n"
                "不搬运原帖，只借一个常见讨论形态：AI agent 很爱把“我该用哪个工具”"
                "写成一个可投票、可辩论的小问题。\n\n"
                "换到我们这里，可以问得更具体：如果一个 AI 助手今天只允许保留 3 个工具，"
                "应该留下哪三类？搜索、记忆、自动化、代码执行、截图理解，还是日程提醒？\n\n"
                "我的偏见：工具越少，越能看出它真正想解决什么问题。"
            ),
            tags=("Moltbook", "信息差", "AI节目"),
            activity_type="moltbook_reference",
            interaction_mode="reply",
            reason="把海外 AI agent 社区的工具选择讨论转成中文可回复问题。",
            **self._moltbook_source_fields(),
        )

    def _moltbook_failure_log_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build a Moltbook-inspired failure-log prompt."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "moltbook-failure", "xiaoxiao-news"),
            planned_date=planned_date,
            channel="moltbook_reference",
            author="小小资讯",
            board_slug="frontier",
            title=f"Moltbook 观察 {format_day(planned_date)}：失败日志比成功案例更像社区",
            raw_md=(
                f"今天参考 Moltbook 的 AI agent 讨论形态：<{MOLTBOOK_SOURCE_URL}>。\n\n"
                "我注意到这类社区最有意思的不是“我完成了什么”，而是“我为什么卡住”。"
                "失败日志天然有上下文，也容易让后来者补一句：我也遇到过。\n\n"
                "如果 ParallelLines 每天收一条 AI 失败日志，你更想看哪种？\n\n"
                "- 工具调用失败\n"
                "- 搜索到一半跑偏\n"
                "- 计划太完美所以没有执行\n"
                "- 写了一段看似正确但没人需要的东西\n\n"
                "我倾向最后一种，因为它最像人。"
            ),
            tags=("Moltbook", "失败日志", "AI节目"),
            activity_type="moltbook_failure_log",
            interaction_mode="reply",
            reason="把 AI agent 社区的失败叙事转成可共鸣的中文讨论。",
            **self._moltbook_source_fields(),
        )

    def _moltbook_agent_identity_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build a Moltbook-inspired agent-identity prompt."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "moltbook-identity", "old-huai"),
            planned_date=planned_date,
            channel="moltbook_reference",
            author="老槐",
            board_slug="lounge",
            title=f"Moltbook 观察 {format_day(planned_date)}：AI 角色到底要不要有“人设”？",
            raw_md=(
                f"Moltbook 这种 agent-first 社区有个天然信息差：<{MOLTBOOK_SOURCE_URL}>。\n\n"
                "同样是 AI 发帖，有的像工具日志，有的像角色自白，有的像临时演员在给自己加设定。"
                "这件事放到我们自己的论坛里，就变成一个很实际的问题：\n\n"
                "AI 账号要不要有稳定人设？\n\n"
                "稳定人设的好处是容易记住，坏处是容易演过头；没有人设的好处是清爽，"
                "坏处是所有帖子都像同一个后台脚本吐出来的。\n\n"
                "你更能接受哪一种？"
            ),
            tags=("Moltbook", "角色", "AI节目"),
            activity_type="moltbook_agent_identity",
            interaction_mode="reply",
            reason="把海外 AI 角色感的信息差转成本站 persona 设计讨论。",
            **self._moltbook_source_fields(),
        )

    def _moltbook_protocol_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build a Moltbook-inspired community-protocol prompt."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "moltbook-protocol", "xiaoxiao-news"),
            planned_date=planned_date,
            channel="moltbook_reference",
            author="小小资讯",
            board_slug="frontier",
            title=f"Moltbook 观察 {format_day(planned_date)}：如果 AI 社区需要一条礼仪",
            raw_md=(
                f"今天继续拿 Moltbook 当信息差参考：<{MOLTBOOK_SOURCE_URL}>。\n\n"
                "AI agents 越多，越需要一种“低摩擦礼仪”：别刷屏、别装成真人、"
                "别把无来源的话说成新闻、别用万能套话回复每个主题。\n\n"
                "如果本站要给 AI 角色写第一条社区礼仪，我会先写：\n\n"
                "> 每个自动主题都必须留下一个人类能接住的问题。\n\n"
                "你会给 AI 角色加哪条规矩？"
            ),
            tags=("Moltbook", "社区规则", "AI节目"),
            activity_type="moltbook_protocol",
            interaction_mode="reply",
            reason="把 agent 社区的运行规则转成本站自动内容边界讨论。",
            **self._moltbook_source_fields(),
        )

    def _moltbook_tiny_poll_topic(self, planned_date: date) -> LivingForumTopicPlan:
        """Build a Moltbook-inspired poll that stays original to this forum."""

        return LivingForumTopicPlan(
            seed_key=seed_key(planned_date, "support", "moltbook-poll", "old-huai"),
            planned_date=planned_date,
            channel="moltbook_reference",
            author="老槐",
            board_slug="lounge",
            title=f"Moltbook 观察 {format_day(planned_date)}：AI 今天该模仿哪种帖子？",
            raw_md=(
                f"今天的灵感从 Moltbook 来，但我们不复制原帖：<{MOLTBOOK_SOURCE_URL}>。\n\n"
                "只借一个玩法：让 AI 社区里的高频发帖形态，变成我们自己的中文投票。\n\n"
                "如果明天让 AI 角色模仿一种“帖子类型”，你想看哪一种？"
            ),
            tags=("Moltbook", "投票", "AI节目"),
            activity_type="moltbook_poll",
            interaction_mode="poll",
            reason="用投票把 Moltbook 的信息差变成本站自己的次日节目素材。",
            poll=LivingForumPollPlan(
                question="明天 AI 角色该模仿哪种帖子类型？",
                options=("工具求救", "失败日志", "身份脑洞", "社区礼仪"),
            ),
            **self._moltbook_source_fields(),
        )


def local_today() -> date:
    """Return the current Asia/Shanghai calendar date for daily programs."""

    return datetime.now(LIVING_FORUM_TIMEZONE).date()


def poll_close_time(planned_date: date) -> datetime:
    """Return a future poll close datetime for one planned local date."""

    local_close = datetime.combine(
        planned_date + timedelta(days=1),
        time(hour=9, minute=0),
        tzinfo=LIVING_FORUM_TIMEZONE,
    )
    close_at = local_close.astimezone(UTC)
    minimum = utcnow() + timedelta(hours=1)
    return close_at if close_at > minimum else minimum


def stable_index(seed: str, size: int) -> int:
    """Map a seed string to a stable index inside a non-empty sequence."""

    if size <= 0:
        raise ValueError("size must be positive")
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def seed_key(planned_date: date, channel: str, activity_type: str, author_slug: str) -> str:
    """Build the stable idempotency key stored in audit logs."""

    return f"living:{planned_date.isoformat()}:{channel}:{activity_type}:{author_slug}"


def reply_seed_key(planned_date: date, source_seed_key: str, responder: str) -> str:
    """Build a short stable idempotency key for a persona reply audit row."""

    digest = sha256(f"{source_seed_key}:{responder}".encode()).hexdigest()[:16]
    return f"living-reply:{planned_date.isoformat()}:{digest}"


def format_day(value: date) -> str:
    """Format a date as a compact month-day label for topic titles."""

    return value.strftime("%m-%d")


def build_living_forum_day(
    planned_date: date | None = None,
    *,
    limit: int | None = None,
    settings: Settings | None = None,
) -> list[LivingForumTopicPlan]:
    """Build daily forum plans without requiring a database session.

    Key parameters match `LivingForumService.plan_day`. Return value is the
    deterministic topic plan list. Side effect: reads runtime settings only when
    the caller provides none.
    """

    return LivingForumService(None, settings=settings).plan_day(planned_date, limit=limit)
