from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import secrets
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.permissions import is_admin
from app.core.security import hash_password
from app.db.base import utcnow
from app.models.forum import Board
from app.models.moderation import Reviewable
from app.models.news import FrontierNewsAiRun, FrontierNewsItem, FrontierNewsSource
from app.models.user import User
from app.schemas.news import (
    FrontierNewsCollectResponse,
    FrontierNewsItemResponse,
    FrontierNewsSourceCreateRequest,
    FrontierNewsSourceResponse,
    FrontierNewsSourceUpdateRequest,
)
from app.services.moderation import ModerationService

FRONTIER_NEWS_PROMPT_VERSION = "frontier-v1"
DEFAULT_REVIEW_BATCH_SIZE = 3
OPEN_REVIEW_STATUSES = {"pending", "claimed", "appealed"}
TERMINAL_ITEM_STATUSES = {"published", "rejected", "duplicate"}
AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "llm",
    "language model",
    "agent",
    "multimodal",
    "transformer",
    "reasoning",
    "rag",
    "生成式",
    "大模型",
    "人工智能",
    "模型",
)
INTERNAL_COPY_MARKERS = (
    "发布/出现了一条",
    "AI 前沿相关的信息",
    "审核",
    "送审",
    "人工核验",
    "人工事实判断",
    "资讯机器人发布",
    "发布到前沿资讯",
    "进入人工审核流程",
    "原文可信度",
    "是否重复",
)


@dataclass(frozen=True)
class DefaultFrontierSource:
    """Default source seed used when the installation has no frontier source rows."""

    key: str
    name: str
    kind: str
    url: str
    config: dict[str, object]
    trust_level: int
    fetch_interval_minutes: int


@dataclass(frozen=True)
class FetchedNewsEntry:
    """Normalized upstream entry returned by RSS/API fetchers before persistence."""

    external_id: str
    title: str
    url: str
    summary: str | None
    author_names: list[str]
    published_at: datetime | None
    raw_payload: dict[str, object]
    image_url: str | None = None


DEFAULT_FRONTIER_SOURCES: tuple[DefaultFrontierSource, ...] = (
    DefaultFrontierSource(
        key="arxiv_ai_llm",
        name="arXiv AI / LLM 论文",
        kind="arxiv",
        url="https://export.arxiv.org/api/query",
        config={
            "categories": ["cs.AI", "cs.CL", "cs.LG"],
            "max_items": 12,
            "review_batch_size": DEFAULT_REVIEW_BATCH_SIZE,
            "keywords": list(AI_KEYWORDS),
        },
        trust_level=90,
        fetch_interval_minutes=240,
    ),
    DefaultFrontierSource(
        key="hacker_news_ai",
        name="Hacker News AI 热点",
        kind="hacker_news",
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        config={
            "max_items": 18,
            "candidate_items": 80,
            "review_batch_size": DEFAULT_REVIEW_BATCH_SIZE,
            "keywords": list(AI_KEYWORDS),
        },
        trust_level=65,
        fetch_interval_minutes=120,
    ),
    DefaultFrontierSource(
        key="github_ai_trending",
        name="GitHub AI 项目动态",
        kind="github_search",
        url="https://api.github.com/search/repositories",
        config={
            "query": "topic:llm stars:>100",
            "sort": "updated",
            "order": "desc",
            "max_items": 15,
            "review_batch_size": DEFAULT_REVIEW_BATCH_SIZE,
            "keywords": list(AI_KEYWORDS),
        },
        trust_level=70,
        fetch_interval_minutes=240,
    ),
    DefaultFrontierSource(
        key="huggingface_blog",
        name="Hugging Face Blog",
        kind="rss",
        url="https://huggingface.co/blog/feed.xml",
        config={
            "max_items": 12,
            "review_batch_size": DEFAULT_REVIEW_BATCH_SIZE,
            "keywords": list(AI_KEYWORDS),
        },
        trust_level=80,
        fetch_interval_minutes=240,
    ),
)


class FrontierNewsService:
    """Collects frontier news, prepares Chinese drafts, and sends them to unified moderation."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Store the database session and resolved runtime settings for service methods."""

        self.session = session
        self.settings = settings or get_settings()

    async def list_sources(self, current_user: User) -> list[FrontierNewsSourceResponse]:
        """Return all configured frontier sources after ensuring system defaults exist."""

        self._require_admin(current_user)
        await self.ensure_system_entities()
        await self.ensure_default_sources()
        await self.session.commit()
        sources = list(
            await self.session.scalars(select(FrontierNewsSource).order_by(FrontierNewsSource.name))
        )
        return [FrontierNewsSourceResponse.from_model(source) for source in sources]

    async def create_source(
        self,
        payload: FrontierNewsSourceCreateRequest,
        current_user: User,
    ) -> FrontierNewsSourceResponse:
        """Create one administrator-managed white-listed frontier source."""

        self._require_admin(current_user)
        existing = await self.session.scalar(
            select(FrontierNewsSource).where(FrontierNewsSource.key == payload.key.strip())
        )
        if existing:
            raise ConflictError("frontier_source_exists", "Frontier news source already exists")
        source = FrontierNewsSource(
            key=payload.key.strip(),
            name=payload.name.strip(),
            kind=payload.kind,
            url=payload.url.strip(),
            config=payload.config,
            enabled=payload.enabled,
            trust_level=payload.trust_level,
            fetch_interval_minutes=payload.fetch_interval_minutes,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return FrontierNewsSourceResponse.from_model(source)

    async def update_source(
        self,
        source_id: str,
        payload: FrontierNewsSourceUpdateRequest,
        current_user: User,
    ) -> FrontierNewsSourceResponse:
        """Update source metadata, fetch cadence, config, or enabled state."""

        self._require_admin(current_user)
        source = await self._get_source(source_id)
        if payload.name is not None:
            source.name = payload.name.strip()
        if payload.url is not None:
            source.url = payload.url.strip()
        if payload.config is not None:
            source.config = payload.config
        if payload.enabled is not None:
            source.enabled = payload.enabled
        if payload.trust_level is not None:
            source.trust_level = payload.trust_level
        if payload.fetch_interval_minutes is not None:
            source.fetch_interval_minutes = payload.fetch_interval_minutes
        await self.session.commit()
        await self.session.refresh(source)
        return FrontierNewsSourceResponse.from_model(source)

    async def collect_all_sources(self, current_user: User) -> FrontierNewsCollectResponse:
        """Run an administrator-triggered collection pass for every enabled source."""

        self._require_admin(current_user)
        return await self.collect_due_sources(force=True)

    async def collect_source(
        self,
        source_id: str,
        current_user: User,
    ) -> FrontierNewsCollectResponse:
        """Run an administrator-triggered collection pass for a single source."""

        self._require_admin(current_user)
        await self.ensure_system_entities()
        await self.ensure_default_sources()
        source = await self._get_source(source_id)
        summary = await self._collect_source(source, force=True)
        await self.session.commit()
        return summary

    async def collect_due_sources(self, *, force: bool = False) -> FrontierNewsCollectResponse:
        """Collect enabled sources due for scheduled execution and queue ready drafts."""

        await self.ensure_system_entities()
        await self.ensure_default_sources()
        statement = select(FrontierNewsSource).where(FrontierNewsSource.enabled.is_(True))
        sources = list(await self.session.scalars(statement.order_by(FrontierNewsSource.name)))
        totals = {
            "source_count": 0,
            "created_count": 0,
            "queued_count": 0,
            "skipped_count": 0,
            "error_count": 0,
        }
        for source in sources:
            if not force and not self._source_due(source):
                continue
            result = await self._collect_source(source, force=force)
            for key in totals:
                totals[key] += getattr(result, key)
        await self.session.commit()
        return FrontierNewsCollectResponse(**totals)

    async def list_items(
        self,
        current_user: User,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FrontierNewsItemResponse]:
        """Return collected materials for the admin source/material panel."""

        self._require_admin(current_user)
        statement = (
            select(FrontierNewsItem)
            .options(
                selectinload(FrontierNewsItem.source),
                selectinload(FrontierNewsItem.reviewed_by),
            )
            .order_by(desc(FrontierNewsItem.created_at))
            .limit(limit)
        )
        if status and status != "all":
            statement = statement.where(FrontierNewsItem.status == status)
        items = list(await self.session.scalars(statement))
        return [FrontierNewsItemResponse.from_model(item) for item in items]

    async def enrich_item(self, item_id: str, current_user: User) -> FrontierNewsItemResponse:
        """Re-run the AI整理 step for a collected item and enqueue it for review if ready."""

        self._require_admin(current_user)
        item = await self._get_item(item_id)
        await self._enrich_and_queue_item(item)
        await self.session.commit()
        return FrontierNewsItemResponse.from_model(await self._get_item(item_id))

    async def queue_item_for_review(
        self,
        item_id: str,
        current_user: User,
        *,
        note: str | None = None,
    ) -> FrontierNewsItemResponse:
        """Manually send an already-prepared item into the unified reviewables queue."""

        self._require_admin(current_user)
        item = await self._get_item(item_id)
        await self._queue_item_for_review(item, note=note)
        await self.session.commit()
        return FrontierNewsItemResponse.from_model(await self._get_item(item_id))

    async def record_reviewable_decision(
        self,
        reviewable: Reviewable,
        *,
        action: str,
        actor: User,
        note: str | None = None,
    ) -> None:
        """Sync a unified moderation decision back to its frontier news material row."""

        item_id = self._reviewable_item_id(reviewable)
        if not item_id:
            return
        item = await self.session.get(FrontierNewsItem, item_id)
        if not item:
            return
        if action == "approve":
            item.status = "published"
            item.topic_id = reviewable.topic_id
        elif action == "reject":
            item.status = "rejected"
        else:
            return
        item.reviewed_by_id = actor.id
        item.reviewed_at = utcnow()
        item.review_note = note

    async def refresh_reviewable_public_copy(self, reviewable: Reviewable) -> None:
        """Rewrite a frontier reviewable's public draft with the current reader-facing template."""

        item_id = self._reviewable_item_id(reviewable)
        if not item_id:
            return
        item = await self.session.get(FrontierNewsItem, item_id)
        if not item:
            return
        raw_md = self._build_topic_markdown(item)
        data = dict(reviewable.data or {})
        fields = dict(data.get("fields") or {})
        data["raw_md"] = raw_md
        data["excerpt"] = raw_md[:180]
        fields["raw_md"] = raw_md
        data["fields"] = fields
        reviewable.data = data

    async def ensure_system_entities(self) -> tuple[User, Board]:
        """Ensure the ordinary bot user and frontier board exist for scheduled publishing."""

        bot = await self.ensure_bot_user()
        board = await self.ensure_frontier_board(owner_id=bot.id)
        return bot, board

    async def ensure_bot_user(self) -> User:
        """Create or normalize the ordinary `资讯机器人` account without login tokens."""

        username = self.settings.frontier_news_bot_username
        email = self.settings.frontier_news_bot_email
        by_username = await self.session.scalar(select(User).where(User.username == username))
        by_email = await self.session.scalar(select(User).where(User.email == email))
        if by_username and by_email and by_username.id != by_email.id:
            raise ConflictError(
                "frontier_news_bot_conflict",
                "Frontier news bot username and email belong to different users",
            )
        bot = by_username or by_email
        if bot is None:
            bot = User(
                username=username,
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(48)),
                display_name=username,
                role="user",
                level=0,
                trust_level=0,
                points_balance=0,
                experience_total=0,
                status="active",
                two_factor_enabled=False,
                profile_visibility="public",
                show_activity=True,
                interface_theme="system",
                locale="zh-CN",
            )
            self.session.add(bot)
            await self.session.flush()
            return bot
        if bot.username != username or bot.email != email:
            raise ConflictError(
                "frontier_news_bot_conflict",
                "Frontier news bot username or email is already used by another account",
            )
        bot.display_name = bot.display_name or username
        bot.role = "user"
        bot.status = "active"
        bot.level = 0
        bot.trust_level = 0
        return bot

    async def ensure_frontier_board(self, *, owner_id: str | None = None) -> Board:
        """Create the `frontier` board or rename the legacy news board when safe."""

        slug = self.settings.frontier_news_board_slug
        board = await self.session.scalar(select(Board).where(Board.slug == slug))
        if board:
            return board
        legacy = await self.session.scalar(
            select(Board).where(
                Board.slug == "news",
                Board.name.in_(["前沿快讯", "前沿资讯"]),
            )
        )
        if legacy:
            legacy.slug = slug
            legacy.name = "前沿资讯"
            legacy.description = "自动汇集 AI、科技、研究论文与开源工具动态，经人工审核后发布。"
            return legacy
        board = Board(
            slug=slug,
            name="前沿资讯",
            description="自动汇集 AI、科技、研究论文与开源工具动态，经人工审核后发布。",
            color="#6366f1",
            owner_id=owner_id,
            visibility="public",
            default_notification_level="normal",
            default_sort="latest",
            topic_count=0,
            post_count=0,
            follower_count=0,
        )
        self.session.add(board)
        await self.session.flush()
        return board

    async def ensure_default_sources(self) -> None:
        """Seed missing default sources while preserving administrator edits."""

        existing_keys = set(await self.session.scalars(select(FrontierNewsSource.key)))
        for spec in DEFAULT_FRONTIER_SOURCES:
            if spec.key in existing_keys:
                continue
            self.session.add(
                FrontierNewsSource(
                    key=spec.key,
                    name=spec.name,
                    kind=spec.kind,
                    url=spec.url,
                    config=spec.config,
                    enabled=True,
                    trust_level=spec.trust_level,
                    fetch_interval_minutes=spec.fetch_interval_minutes,
                )
            )
        await self.session.flush()

    async def _collect_source(
        self,
        source: FrontierNewsSource,
        *,
        force: bool,
    ) -> FrontierNewsCollectResponse:
        """Fetch one source, persist new materials, and queue AI-ready reviewables."""

        del force
        review_batch_size = self._review_batch_size(source)
        source_count = 1
        created_count = 0
        queued_count = 0
        skipped_count = 0
        error_count = 0
        try:
            entries = await self._fetch_source_entries(source)
        except Exception as exc:
            source.last_error = str(exc)[:1000] or type(exc).__name__
            return FrontierNewsCollectResponse(
                source_count=source_count,
                created_count=0,
                queued_count=0,
                skipped_count=0,
                error_count=1,
            )
        source.last_checked_at = utcnow()
        source.last_error = None
        for entry in entries:
            if queued_count >= review_batch_size:
                break
            item, created = await self._upsert_entry(source, entry)
            if not created:
                skipped_count += 1
                continue
            created_count += 1
            try:
                queued_before = item.reviewable_id
                await self._enrich_and_queue_item(item)
                if item.reviewable_id and item.reviewable_id != queued_before:
                    queued_count += 1
            except Exception as exc:
                item.status = "failed"
                item.ai_error = str(exc)[:1000] or type(exc).__name__
                error_count += 1
        return FrontierNewsCollectResponse(
            source_count=source_count,
            created_count=created_count,
            queued_count=queued_count,
            skipped_count=skipped_count,
            error_count=error_count,
        )

    async def _fetch_source_entries(self, source: FrontierNewsSource) -> list[FetchedNewsEntry]:
        """Dispatch to the fetcher matching the configured source kind."""

        if source.kind == "rss":
            return await self._fetch_rss_entries(source)
        if source.kind == "arxiv":
            return await self._fetch_arxiv_entries(source)
        if source.kind == "hacker_news":
            return await self._fetch_hacker_news_entries(source)
        if source.kind == "github_search":
            return await self._fetch_github_entries(source)
        raise ValidationError(
            "frontier_source_kind_invalid", "Unsupported frontier news source kind"
        )

    async def _fetch_rss_entries(self, source: FrontierNewsSource) -> list[FetchedNewsEntry]:
        """Fetch and normalize RSS or Atom feed entries."""

        root = ET.fromstring(await self._read_url(source.url))
        entries: list[FetchedNewsEntry] = []
        nodes = root.findall(".//item") or [
            node for node in root if _local_name(node.tag) == "entry"
        ]
        for node in nodes[: self._max_items(source)]:
            title = _clean_text(_child_text(node, "title"))
            link = _entry_link(node)
            if not title or not link:
                continue
            raw_summary = (
                _child_text(node, "description")
                or _child_text(node, "summary")
                or _child_text(node, "content")
            )
            summary = _clean_text(raw_summary)
            author_value = _child_text(node, "author") or _child_text(node, "creator")
            entries.append(
                FetchedNewsEntry(
                    external_id=_clean_text(_child_text(node, "guid")) or link,
                    title=title,
                    url=link,
                    summary=summary or None,
                    author_names=[_clean_text(author_value)] if author_value else [],
                    published_at=_parse_datetime(
                        _child_text(node, "published")
                        or _child_text(node, "updated")
                        or _child_text(node, "pubDate")
                    ),
                    raw_payload=_safe_payload(_element_to_dict(node)),
                    image_url=_entry_image_url(node) or _html_image_url(raw_summary),
                )
            )
        return self._filter_entries(source, entries)

    async def _fetch_arxiv_entries(self, source: FrontierNewsSource) -> list[FetchedNewsEntry]:
        """Query arXiv Atom API for configured AI categories."""

        categories = [str(item) for item in source.config.get("categories", []) if str(item)]
        entries: list[FetchedNewsEntry] = []
        failed_queries: list[str] = []
        max_items = self._max_items(source)
        for category in categories or ["cs.AI"]:
            if len(entries) >= max_items:
                break
            params = urllib.parse.urlencode(
                {
                    "search_query": f"cat:{category}",
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": str(self._arxiv_category_limit(source, len(categories) or 1)),
                }
            )
            try:
                root = ET.fromstring(await self._read_url(f"{source.url}?{params}"))
            except (TimeoutError, OSError, ET.ParseError) as exc:
                failed_queries.append(f"{category}: {exc}")
                continue
            for node in [child for child in root if _local_name(child.tag) == "entry"]:
                title = _clean_text(_child_text(node, "title"))
                link = _entry_link(node) or _clean_text(_child_text(node, "id"))
                if not title or not link:
                    continue
                authors = [
                    _clean_text(_child_text(author, "name"))
                    for author in node
                    if _local_name(author.tag) == "author"
                ]
                entries.append(
                    FetchedNewsEntry(
                        external_id=_clean_text(_child_text(node, "id")) or link,
                        title=title,
                        url=link,
                        summary=_clean_text(_child_text(node, "summary")) or None,
                        author_names=[author for author in authors if author],
                        published_at=_parse_datetime(
                            _child_text(node, "published") or _child_text(node, "updated")
                        ),
                        raw_payload=_safe_payload(_element_to_dict(node)),
                    ),
                )
                if len(entries) >= max_items:
                    break
        if not entries and failed_queries:
            raise OSError("; ".join(failed_queries)[:1000])
        return self._filter_entries(source, entries)

    async def _fetch_hacker_news_entries(
        self, source: FrontierNewsSource
    ) -> list[FetchedNewsEntry]:
        """Fetch Hacker News top stories and keep AI-related discussions or links."""

        ids = await self._read_json(source.url)
        if not isinstance(ids, list):
            return []
        entries: list[FetchedNewsEntry] = []
        candidate_count = int(source.config.get("candidate_items") or 60)
        for item_id in ids[:candidate_count]:
            item = await self._read_json(
                f"https://hacker-news.firebaseio.com/v0/item/{urllib.parse.quote(str(item_id))}.json"
            )
            if not isinstance(item, dict) or item.get("type") != "story":
                continue
            title = _clean_text(str(item.get("title") or ""))
            link = str(item.get("url") or f"https://news.ycombinator.com/item?id={item_id}")
            if not title or not self._matches_keywords(source, f"{title} {link}"):
                continue
            entries.append(
                FetchedNewsEntry(
                    external_id=str(item.get("id") or item_id),
                    title=title,
                    url=link,
                    summary=(
                        f"HN {item.get('score') or 0} points / "
                        f"{item.get('descendants') or 0} comments"
                    ),
                    author_names=[str(item.get("by"))] if item.get("by") else [],
                    published_at=datetime.fromtimestamp(int(item["time"]), tz=utcnow().tzinfo)
                    if item.get("time")
                    else None,
                    raw_payload=_safe_payload(item),
                )
            )
            if len(entries) >= self._max_items(source):
                break
        return entries

    async def _fetch_github_entries(self, source: FrontierNewsSource) -> list[FetchedNewsEntry]:
        """Fetch recently updated GitHub repositories matching the configured query."""

        query = str(source.config.get("query") or "topic:ai")
        params = urllib.parse.urlencode(
            {
                "q": query,
                "sort": str(source.config.get("sort") or "updated"),
                "order": str(source.config.get("order") or "desc"),
                "per_page": str(self._max_items(source)),
            }
        )
        payload = await self._read_json(f"{source.url}?{params}")
        items = payload.get("items", []) if isinstance(payload, dict) else []
        entries: list[FetchedNewsEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = _clean_text(str(item.get("full_name") or item.get("name") or ""))
            link = str(item.get("html_url") or "")
            if not title or not link:
                continue
            description = _clean_text(str(item.get("description") or ""))
            owner = item.get("owner")
            owner_avatar = (
                _safe_image_url(str(owner.get("avatar_url") or ""))
                if isinstance(owner, dict)
                else None
            )
            entries.append(
                FetchedNewsEntry(
                    external_id=str(item.get("node_id") or item.get("id") or link),
                    title=title,
                    url=link,
                    summary=(
                        f"{description}\nStars: {item.get('stargazers_count') or 0}; "
                        f"language: {item.get('language') or 'unknown'}"
                    ),
                    author_names=[str((item.get("owner") or {}).get("login"))]
                    if isinstance(item.get("owner"), dict)
                    else [],
                    published_at=_parse_datetime(
                        str(item.get("pushed_at") or item.get("updated_at") or "")
                    ),
                    raw_payload=_safe_payload(item),
                    image_url=owner_avatar,
                )
            )
        return self._filter_entries(source, entries)

    async def _upsert_entry(
        self,
        source: FrontierNewsSource,
        entry: FetchedNewsEntry,
    ) -> tuple[FrontierNewsItem, bool]:
        """Insert a new material row unless source/external ID or URL hash already exists."""

        canonical_url = _canonicalize_url(entry.url)
        url_hash = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        existing = await self.session.scalar(
            select(FrontierNewsItem).where(
                or_(
                    FrontierNewsItem.canonical_url_hash == url_hash,
                    (FrontierNewsItem.source_id == source.id)
                    & (FrontierNewsItem.external_id == entry.external_id),
                )
            )
        )
        if existing:
            return existing, False
        raw_payload = dict(entry.raw_payload)
        if entry.image_url:
            raw_payload["image_url"] = entry.image_url
        item = FrontierNewsItem(
            source_id=source.id,
            source=source,
            external_id=entry.external_id[:255],
            canonical_url=canonical_url,
            canonical_url_hash=url_hash,
            title=entry.title[:500],
            summary=entry.summary,
            author_names=entry.author_names[:12],
            published_at=entry.published_at,
            raw_payload=raw_payload,
            item_type="news",
            suggested_tags=[],
            ai_key_points=[],
            ai_risk_flags=[],
            score=self._score_entry(source, entry),
            status="collected",
        )
        self.session.add(item)
        await self.session.flush()
        return item, True

    async def _enrich_and_queue_item(self, item: FrontierNewsItem) -> None:
        """Apply local AI整理 and enqueue the material into unified moderation when ready."""

        if item.status in TERMINAL_ITEM_STATUSES:
            return
        item.status = "ai_pending"
        run = FrontierNewsAiRun(
            item_id=item.id,
            status="succeeded",
            provider=self.settings.frontier_news_ai_provider,
            model_name=self.settings.frontier_news_ai_model,
            prompt_version=FRONTIER_NEWS_PROMPT_VERSION,
            input_tokens=0,
            output_tokens=0,
            cost_units=0,
            created_at=utcnow(),
        )
        self.session.add(run)
        try:
            draft = self._local_ai_prepare(item)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:1000] or type(exc).__name__
            item.status = "failed"
            item.ai_error = run.error
            return
        item.item_type = draft["item_type"]
        item.suggested_tags = draft["tags"]
        item.ai_title_zh = draft["title"]
        item.ai_summary_zh = draft["summary"]
        item.ai_key_points = draft["key_points"]
        item.ai_why_it_matters = draft["why_it_matters"]
        item.ai_risk_flags = draft["risk_flags"]
        item.ai_review_suggestion = draft["review_suggestion"]
        item.ai_model_name = run.model_name
        item.ai_processed_at = utcnow()
        item.ai_error = None
        item.status = "collected"
        if draft["review_suggestion"] != "skip":
            await self._queue_item_for_review(item)

    async def _queue_item_for_review(
        self, item: FrontierNewsItem, *, note: str | None = None
    ) -> None:
        """Create a `queued_topic` reviewable so existing approval publishes the bot topic."""

        bot, board = await self.ensure_system_entities()
        if item.reviewable_id:
            existing = await self.session.get(Reviewable, item.reviewable_id)
            if existing and existing.status in OPEN_REVIEW_STATUSES | {"approved"}:
                item.status = (
                    "review_pending" if existing.status in OPEN_REVIEW_STATUSES else item.status
                )
                return
        if item.score < 20:
            item.ai_review_suggestion = "skip"
            return
        title = (item.ai_title_zh or item.title).strip()[:180]
        raw_md = self._build_topic_markdown(item, note=note)
        tags = self._topic_tags(item)
        reviewable = await ModerationService(self.session).create_content_reviewable(
            current_user=bot,
            reviewable_type="queued_topic",
            board=board,
            sanitized_fields={"title": title, "raw_md": raw_md},
            matched_fields=("frontier_news",),
            data={
                "title": title,
                "raw_md": raw_md,
                "tags": tags,
                "pinned": False,
                "featured": False,
                "board_slug": board.slug,
                "frontier_news_item_id": item.id,
                "source_name": item.source.name if item.source else None,
                "source_url": item.canonical_url,
                "original_title": item.title,
                "ai_risk_flags": item.ai_risk_flags,
            },
            source="frontier_news",
            source_summary=f"资讯机器人整理：{title}",
        )
        item.reviewable_id = reviewable.id
        item.status = "review_pending"

    def _local_ai_prepare(self, item: FrontierNewsItem) -> dict[str, Any]:
        """Produce a deterministic Chinese draft replaceable by a real AI provider."""

        text = f"{item.title}\n{item.summary or ''}"
        item_type = self._classify_item(item, text)
        tags = self._suggest_tags(text, item_type)
        title = self._chinese_title(item.title, item_type)
        summary = self._chinese_summary(item)
        key_points = self._key_points(item)
        risk_flags = self._risk_flags(item)
        review_suggestion = "ready" if item.score >= 35 else "needs_edit"
        if item.score < 20:
            review_suggestion = "skip"
        return {
            "item_type": item_type,
            "tags": tags,
            "title": title,
            "summary": summary,
            "key_points": key_points,
            "why_it_matters": self._why_it_matters(item, item_type),
            "risk_flags": risk_flags,
            "review_suggestion": review_suggestion,
        }

    def _build_topic_markdown(self, item: FrontierNewsItem, *, note: str | None = None) -> str:
        """Render a source-first news card without generic generated commentary."""

        del note
        lines = [
            ":::news-card",
            self._original_meta_line(item),
        ]
        image_url = self._image_url(item)
        if image_url:
            lines.append(f"![{_markdown_label(item.title)}]({image_url})")
        lines.extend(
            [
                f"[{_markdown_label(item.title)}]({item.canonical_url})",
                self._card_summary(item),
                ":::",
            ]
        )
        return "\n".join(line for line in lines if line).strip()

    def _image_url(self, item: FrontierNewsItem) -> str:
        """Return a safe card image URL extracted from normalized or upstream payload data."""

        payload = item.raw_payload if isinstance(item.raw_payload, dict) else {}
        direct = _first_image_candidate(
            payload,
            keys=("image_url", "image", "thumbnail", "thumbnail_url", "og_image"),
        )
        if direct:
            return direct
        owner = payload.get("owner")
        if isinstance(owner, dict):
            owner_avatar = _first_image_candidate(owner, keys=("avatar_url",))
            if owner_avatar:
                return owner_avatar
        return _first_image_candidate(payload)

    def _card_summary(self, item: FrontierNewsItem) -> str:
        """Return the summary shown inside the source card, falling back when upstream is sparse."""

        summary = re.sub(r"^一句话[：:]\s*", "", _clean_text(item.ai_summary_zh)).strip()
        if (
            summary
            and not _contains_internal_copy(summary)
            and not _looks_like_low_value_summary(summary)
        ):
            return _truncate(summary, 420)
        original_excerpt = self._original_excerpt(item)
        if original_excerpt:
            return original_excerpt
        return self._focus_hint(item)

    def _original_meta_line(self, item: FrontierNewsItem) -> str:
        """Build the source/date/author metadata line shown directly under the original link."""

        parts = [f"来源：{item.source.name if item.source else '白名单来源'}"]
        if item.published_at:
            parts.append(f"原文时间：{item.published_at.date().isoformat()}")
        if item.author_names:
            parts.append(f"作者/来源账号：{', '.join(item.author_names[:6])}")
        return " · ".join(parts)

    def _original_excerpt(self, item: FrontierNewsItem) -> str:
        """Return a short upstream excerpt for the source-first repost block."""

        summary = _clean_text(item.summary)
        if summary and summary.lower() != _clean_text(item.title).lower():
            return _truncate(summary, 360)
        return ""

    def _public_key_points(self, item: FrontierNewsItem) -> list[str]:
        """Return public content points with any moderation/process bullets removed."""

        points = [
            _clean_text(point)
            for point in item.ai_key_points
            if _clean_text(point)
            and _clean_text(point).lower() != _clean_text(item.title).lower()
            and not _contains_internal_copy(_clean_text(point))
            and not _looks_like_low_value_point(_clean_text(point))
        ]
        if len(points) < 2:
            points = []
        for fallback in self._key_points(item):
            if len(points) >= 3:
                break
            if (
                fallback not in points
                and fallback.lower() != _clean_text(item.title).lower()
                and not _contains_internal_copy(fallback)
                and not _looks_like_low_value_point(fallback)
            ):
                points.append(fallback)
        return points[:3] or self._content_takeaways(item)[:3]

    def _public_interest(self, item: FrontierNewsItem) -> str:
        """Return public reader-interest copy, ignoring stored review guidance when present."""

        interest = _clean_text(item.ai_why_it_matters)
        if interest and not _contains_internal_copy(interest):
            return interest
        return self._why_it_matters(item, item.item_type)

    def _topic_tags(self, item: FrontierNewsItem) -> list[str]:
        """Return normalized-looking tag labels while keeping within forum request limits."""

        tags = ["前沿资讯", *item.suggested_tags]
        unique: list[str] = []
        for tag in tags:
            safe = str(tag).strip()[:48]
            if safe and safe not in unique:
                unique.append(safe)
        return unique[:8]

    def _score_entry(self, source: FrontierNewsSource, entry: FetchedNewsEntry) -> int:
        """Score relevance from source trust, keyword hits, and metadata completeness."""

        text = f"{entry.title} {entry.summary or ''} {entry.url}".lower()
        keyword_hits = sum(1 for keyword in self._keywords(source) if keyword.lower() in text)
        score = int(source.trust_level * 0.55) + min(30, keyword_hits * 8)
        if entry.summary:
            score += 8
        if entry.published_at:
            score += 5
        if "github.com" in entry.url:
            score += 5
        return max(0, min(100, score))

    def _source_due(self, source: FrontierNewsSource) -> bool:
        """Return whether a source should run in the current scheduled bucket."""

        if source.last_checked_at is None:
            return True
        return source.last_checked_at <= utcnow() - timedelta(minutes=source.fetch_interval_minutes)

    def _classify_item(self, item: FrontierNewsItem, text: str) -> str:
        """Classify material from source kind first, then text keywords for safe fallbacks."""

        source_kind = item.source.kind if item.source else None
        if source_kind == "arxiv":
            return "paper"
        if source_kind == "github_search":
            return "tool"
        if source_kind == "hacker_news":
            return "discussion"
        lowered = text.lower()
        if "arxiv" in lowered or "paper" in lowered or "论文" in lowered:
            return "paper"
        if "github" in lowered or "repository" in lowered or "repo" in lowered:
            return "tool"
        if "comments" in lowered or "hacker news" in lowered:
            return "discussion"
        return "news"

    def _suggest_tags(self, text: str, item_type: str) -> list[str]:
        """Suggest concise Chinese forum tags from keywords and item type."""

        lowered = text.lower()
        tags = ["论文" if item_type == "paper" else "工具" if item_type == "tool" else "动态"]
        keyword_tags = (
            ("llm", "大模型"),
            ("agent", "智能体"),
            ("multimodal", "多模态"),
            ("rag", "RAG"),
            ("reasoning", "推理"),
            ("open source", "开源"),
            ("github", "开源"),
        )
        for keyword, tag in keyword_tags:
            if keyword in lowered and tag not in tags:
                tags.append(tag)
        return tags[:6]

    def _chinese_title(self, title: str, item_type: str) -> str:
        """Create a Chinese review title while preserving source nouns for fact safety."""

        prefix = {"paper": "论文", "tool": "开源", "discussion": "社区", "news": "动态"}.get(
            item_type,
            "动态",
        )
        cleaned = _clean_text(title).strip(" -—")
        if _contains_cjk(cleaned):
            return cleaned[:180]
        return f"【{prefix}】{cleaned}"[:180]

    def _chinese_summary(self, item: FrontierNewsItem) -> str:
        """Create a reader-facing Chinese summary from available title and source excerpt."""

        title = _clean_text(item.title)
        summary = _clean_text(item.summary)
        if summary and summary.lower() != title.lower():
            return _truncate(summary, 420)
        return self._focus_hint(item)

    def _key_points(self, item: FrontierNewsItem) -> list[str]:
        """Extract concise reader-facing takeaways from title and summary text."""

        sentences = _split_sentences(f"{item.title}. {item.summary or ''}")
        points = [_truncate(sentence, 140) for sentence in sentences if sentence][:2]
        for fallback in self._content_takeaways(item):
            if len(points) >= 3:
                break
            if fallback not in points:
                points.append(fallback)
        return points[:3]

    def _why_it_matters(self, item: FrontierNewsItem, item_type: str) -> str:
        """Explain practical reader interest without mentioning the moderation workflow."""

        type_label = {"paper": "研究方向", "tool": "开源工具", "discussion": "社区反馈"}.get(
            item_type,
            "行业动态",
        )
        title = item.title.lower()
        if "computer use" in title or "agent" in title:
            return (
                "如果你关注 AI 智能体，这类内容可以帮助判断模型从聊天走向实际操作电脑、"
                "调用工具和完成任务的进展。"
            )
        if item_type == "tool":
            return (
                "如果你在选型或跟踪开源生态，可以关注它解决的问题、集成成本、"
                "许可证和社区活跃度。"
            )
        if item_type == "paper":
            return (
                "如果你跟踪研究进展，可以关注它提出的问题、方法改动、实验结果，"
                "以及是否已经有可复现资源。"
            )
        return f"这条{type_label}有助于快速了解 AI 技术、产品或生态的最新变化。"

    def _focus_hint(self, item: FrontierNewsItem) -> str:
        """Infer one short reading guide from title keywords when no excerpt exists."""

        lowered = item.title.lower()
        hints: list[str] = []
        if "computer use" in lowered:
            hints.append("它关注能操作电脑界面或软件流程的 Computer Use Agents")
        if "agent" in lowered:
            hints.append("核心关键词是智能体/Agent")
        if "local" in lowered:
            hints.append("标题强调本地运行，可能涉及隐私、成本或部署门槛")
        if "fast" in lowered:
            hints.append("标题强调速度，可能与响应延迟或执行效率有关")
        if not hints:
            return "原始来源没有提供更长摘要，可先根据标题和原文链接了解具体内容。"
        return "；".join(hints) + "。"

    def _content_takeaways(self, item: FrontierNewsItem) -> list[str]:
        """Build fallback public takeaways that describe the news content."""

        title = _clean_text(item.title)
        takeaways: list[str] = []
        lowered = title.lower()
        if "computer use" in lowered:
            takeaways.append(
                "内容方向：让 AI 智能体执行电脑操作任务，例如打开应用、点击界面或完成多步骤流程。"
            )
        if "local" in lowered:
            takeaways.append("看点之一：本地运行通常意味着更低延迟、隐私更可控，也可能降低云端调用依赖。")
        if "agent" in lowered:
            takeaways.append("看点之一：Agent 能力通常涉及任务规划、工具调用、环境观察和错误恢复。")
        if item.summary:
            takeaways.append(f"摘要补充：{_truncate(_clean_text(item.summary), 140)}")
        else:
            takeaways.append("原文未提供长摘要，建议点开来源查看功能细节、演示和限制。")
        if not takeaways:
            takeaways.append(f"主题聚焦：{title}")
        return takeaways

    def _risk_flags(self, item: FrontierNewsItem) -> list[str]:
        """Generate human-review reminders rather than making factual claims."""

        flags = ["需人工核验原文"]
        if item.score < 35:
            flags.append("相关性分数偏低")
        if not item.summary:
            flags.append("来源摘要不足")
        if item.source and item.source.kind in {"hacker_news", "github_search"}:
            flags.append("社区/项目热度不等同于事实确认")
        return flags

    def _filter_entries(
        self,
        source: FrontierNewsSource,
        entries: list[FetchedNewsEntry],
    ) -> list[FetchedNewsEntry]:
        """Apply optional keyword filters configured per source."""

        keywords = self._keywords(source)
        if not keywords:
            return entries[: self._max_items(source)]
        filtered = [
            entry
            for entry in entries
            if self._matches_keywords(source, f"{entry.title} {entry.summary or ''} {entry.url}")
        ]
        return filtered[: self._max_items(source)]

    def _matches_keywords(self, source: FrontierNewsSource, text: str) -> bool:
        """Return true when text contains any configured source keyword."""

        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in self._keywords(source))

    def _keywords(self, source: FrontierNewsSource) -> list[str]:
        """Read keyword filters from source config with robust type coercion."""

        values = source.config.get("keywords") if isinstance(source.config, dict) else None
        if values is None:
            return list(AI_KEYWORDS)
        if not isinstance(values, list):
            return []
        return [str(value) for value in values if str(value).strip()]

    def _max_items(self, source: FrontierNewsSource) -> int:
        """Read and bound per-source max item count to keep one run predictable."""

        raw_value = source.config.get("max_items") if isinstance(source.config, dict) else None
        try:
            value = int(raw_value or 10)
        except (TypeError, ValueError):
            value = 10
        return max(1, min(25, value))

    def _review_batch_size(self, source: FrontierNewsSource) -> int:
        """Read the per-source count of new reviewables to enqueue during one collect pass."""

        raw_value = (
            source.config.get("review_batch_size") if isinstance(source.config, dict) else None
        )
        try:
            value = int(raw_value or DEFAULT_REVIEW_BATCH_SIZE)
        except (TypeError, ValueError):
            value = DEFAULT_REVIEW_BATCH_SIZE
        return max(1, min(10, value))

    def _arxiv_category_limit(self, source: FrontierNewsSource, category_count: int) -> int:
        """Return the bounded per-category arXiv request size used to avoid slow broad queries."""

        raw_value = (
            source.config.get("arxiv_category_items") if isinstance(source.config, dict) else None
        )
        try:
            configured = int(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            configured = None
        if configured:
            return max(1, min(10, configured))
        safe_category_count = max(1, category_count)
        return max(
            2,
            min(6, (self._max_items(source) + safe_category_count - 1) // safe_category_count),
        )

    async def _get_source(self, source_id: str) -> FrontierNewsSource:
        """Load one source or raise a typed not-found error."""

        source = await self.session.get(FrontierNewsSource, source_id)
        if not source:
            raise NotFoundError("frontier_source_not_found", "Frontier news source not found")
        return source

    async def _get_item(self, item_id: str) -> FrontierNewsItem:
        """Load one material with source/reviewer relationships or raise not found."""

        item = await self.session.scalar(
            select(FrontierNewsItem)
            .options(
                selectinload(FrontierNewsItem.source),
                selectinload(FrontierNewsItem.reviewed_by),
            )
            .where(FrontierNewsItem.id == item_id)
        )
        if not item:
            raise NotFoundError("frontier_news_item_not_found", "Frontier news item not found")
        return item

    async def _read_url(self, url: str) -> str:
        """Read a URL in a thread so scheduled network IO does not block the event loop."""

        timeout = self.settings.frontier_news_request_timeout_seconds
        return await asyncio.to_thread(_read_url_sync, url, timeout)

    async def _read_json(self, url: str) -> Any:
        """Read and decode a JSON URL with the same worker-safe timeout policy."""

        return json.loads(await self._read_url(url))

    def _reviewable_item_id(self, reviewable: Reviewable) -> str | None:
        """Extract the frontier material ID from reviewable private data when present."""

        value = reviewable.data.get("frontier_news_item_id") if reviewable.data else None
        return str(value) if value else None

    def _require_admin(self, current_user: User) -> None:
        """Restrict source/material administration to site admins only."""

        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Administrator access required")


def _read_url_sync(url: str, timeout: float) -> str:
    """Perform the blocking urllib request with a project user-agent and UTF-8 fallback."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ParallelLines FrontierNewsBot/0.1 (+https://parallellines.local)",
            "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _local_name(tag: str) -> str:
    """Return an XML tag's local name without namespace braces."""

    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(node: ET.Element, name: str) -> str:
    """Find the first direct child with matching local name and return its text."""

    for child in node:
        if _local_name(child.tag) == name:
            return child.text or ""
    return ""


def _entry_link(node: ET.Element) -> str:
    """Extract a link from RSS text nodes or Atom link href attributes."""

    text_link = _clean_text(_child_text(node, "link"))
    if text_link:
        return text_link
    for child in node:
        if _local_name(child.tag) == "link" and child.attrib.get("href"):
            return child.attrib["href"]
    return ""


def _entry_image_url(node: ET.Element) -> str | None:
    """Extract an image URL from common RSS/Atom media, enclosure, or image children."""

    for child in node:
        name = _local_name(child.tag)
        attributes = child.attrib
        if name in {"thumbnail", "image"}:
            raw_url = (
                attributes.get("url")
                or attributes.get("href")
                or attributes.get("src")
                or child.text
            )
            image_url = _safe_image_url(
                raw_url
            )
            if image_url:
                return image_url
        if name in {"content", "enclosure"}:
            media_type = str(attributes.get("type") or "").lower()
            medium = str(attributes.get("medium") or "").lower()
            if media_type.startswith("image/") or medium == "image":
                image_url = _safe_image_url(
                    attributes.get("url") or attributes.get("href") or attributes.get("src")
                )
                if image_url:
                    return image_url
    return None


def _html_image_url(value: str | None) -> str | None:
    """Extract the first safe image source from an HTML summary string."""

    if not value:
        return None
    match = re.search(r"<img\b[^>]*\bsrc=['\"]([^'\"]+)['\"]", value, flags=re.IGNORECASE)
    return _safe_image_url(match.group(1)) if match else None


def _safe_image_url(value: object) -> str | None:
    """Validate an upstream image URL before putting it into generated Markdown."""

    url = str(value or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    parsed = urllib.parse.urlsplit(url)
    if not parsed.netloc:
        return None
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.query,
            "",
        )
    )


def _first_image_candidate(
    payload: dict[str, object],
    *,
    keys: tuple[str, ...] = ("image_url", "image", "thumbnail", "thumbnail_url", "url", "href"),
) -> str:
    """Find a safe image URL in a shallow payload dictionary or nested attributes block."""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            image_url = _safe_image_url(value)
            if image_url:
                return image_url
        if isinstance(value, dict):
            nested = _first_image_candidate(value)
            if nested:
                return nested
    attributes = payload.get("attributes")
    if isinstance(attributes, dict):
        nested = _first_image_candidate(attributes)
        if nested:
            return nested
    return ""


def _element_to_dict(node: ET.Element) -> dict[str, object]:
    """Convert shallow XML children into a serializable diagnostic payload."""

    payload: dict[str, object] = {}
    for child in node:
        name = _local_name(child.tag)
        if child.attrib:
            payload[name] = {"text": child.text or "", "attributes": dict(child.attrib)}
        elif child.text:
            payload[name] = child.text
    return payload


def _safe_payload(value: Any) -> dict[str, object]:
    """Truncate arbitrary upstream payload data before storing it in JSON columns."""

    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        encoded = json.dumps(str(value), ensure_ascii=False)
    truncated = encoded[:8000]
    try:
        decoded = json.loads(truncated)
    except json.JSONDecodeError:
        return {"raw": truncated}
    return decoded if isinstance(decoded, dict) else {"items": decoded}


def _clean_text(value: str | None) -> str:
    """Normalize whitespace, strip HTML tags, and decode HTML entities."""

    if not value:
        return ""
    decoded = html.unescape(value)
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", without_tags).strip()


def _canonicalize_url(url: str) -> str:
    """Normalize URL fragments and noisy tracking query parameters for deduplication."""

    parsed = urllib.parse.urlsplit(url.strip())
    query_items = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "fbclid", "gclid"}
    ]
    query = urllib.parse.urlencode(sorted(query_items), doseq=True)
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            parsed.path or "/",
            query,
            "",
        )
    )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse common RSS, Atom, and JSON datetime strings into aware datetimes."""

    if not value:
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=utcnow().tzinfo)
    except (TypeError, ValueError):
        return None


def _contains_cjk(value: str) -> bool:
    """Return true if text already contains Chinese/Japanese/Korean characters."""

    return bool(re.search(r"[\u3400-\u9fff]", value))


def _contains_internal_copy(value: str) -> bool:
    """Return true when generated copy leaks moderation/process wording unsuitable for readers."""

    return any(marker in value for marker in INTERNAL_COPY_MARKERS)


def _looks_like_low_value_point(value: str) -> bool:
    """Return true for fragments that are too short or look like broken title pieces."""

    cleaned = _clean_text(value)
    if len(cleaned) < 8:
        return True
    return bool(re.match(r"^\d+\s*[:：]", cleaned))


def _looks_like_low_value_summary(value: str) -> bool:
    """Return true when a summary only restates source/title metadata."""

    cleaned = _clean_text(value)
    return (
        cleaned.startswith("这条资讯来自")
        or "主题是「" in cleaned
        or _contains_internal_copy(cleaned)
    )


def _markdown_label(value: str, max_length: int = 150) -> str:
    """Return a safe, bounded label for the small Markdown link/image renderer."""

    label = re.sub(r"[\[\]\n\r]", " ", _clean_text(value))
    return _truncate(label, max_length) or "原文"


def _truncate(value: str, max_length: int) -> str:
    """Trim text to a maximum length without leaving extra whitespace."""

    cleaned = _clean_text(value)
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 1].rstrip()}…"


def _split_sentences(value: str) -> list[str]:
    """Split source text into simple sentence-like chunks for key point extraction."""

    cleaned = _clean_text(value)
    return [
        part.strip(" .。;；")
        for part in re.split(r"[。!?！？;；]\s*|(?<!\d)\.(?!\d)\s*", cleaned)
        if part.strip()
    ]
