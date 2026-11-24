from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.core.personas import seeded_persona_kind
from app.db.base import as_shanghai_datetime, as_utc_datetime, utcnow
from app.models.forum import Board, Post, Topic
from app.models.moderation import AuditLog
from app.models.news import FrontierNewsSource
from app.models.user import User
from app.schemas.forum import TopicCreateRequest
from app.services import overseas_content
from app.services.forum import ForumService
from app.services.frontier_news import AI_KEYWORDS, FetchedNewsEntry, FrontierNewsService
from app.services.frontier_news import _markdown_label as frontier_markdown_label
from scripts import collect_weibo_hot_search as weibo

ContentChannel = Literal["news", "sports", "hot_search", "overseas"]
SLOT_ACTION = "scheduled_content_published"
SOURCE_ACTION = "scheduled_content_source"
EVENT_ACTION = "scheduled_content_event"
AUDIT_TARGET = "scheduled_content"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT = 10.0
TOTAL_TIMEOUT = 25.0
MAX_NEWS_AGE = timedelta(hours=48)


@dataclass(frozen=True)
class ContentIdentity:
    """Bind a scheduled channel to its existing managed account and public board."""

    username: str
    email: str
    board_slug: str
    tags: tuple[str, ...]


IDENTITIES: dict[ContentChannel, ContentIdentity] = {
    "news": ContentIdentity(
        "小小资讯", "xiaoxiao-zixun@pingxingxian.space", "frontier", ("热点资讯",)
    ),
    "sports": ContentIdentity(
        "小小鸡仔", "xiaoxiao-jizai@pingxingxian.space", "sports", ("体坛快讯",)
    ),
    "hot_search": ContentIdentity(
        "小瓜同学", "xiaogua@pingxingxian.space", "lounge", ("热搜闲聊",)
    ),
    "overseas": ContentIdentity(
        "小瓜同学", "xiaogua@pingxingxian.space", "lounge", ("海外动态",)
    ),
}
FEEDS: dict[str, tuple[tuple[str, str, tuple[str, ...]], ...]] = {
    "news": (
        ("OpenAI 官方资讯", "https://openai.com/news/rss.xml", ("openai.com",)),
        ("Google 官方博客", "https://blog.google/rss/", ("blog.google",)),
    ),
    "sports": (
        (
            "BBC Sport",
            "https://feeds.bbci.co.uk/sport/rss.xml",
            ("feeds.bbci.co.uk", "www.bbc.com", "www.bbc.co.uk"),
        ),
    ),
}


@dataclass(frozen=True)
class SourcedDraft:
    """Hold a source-bound post and its cross-slot duplicate identities, without I/O."""

    title: str
    raw_md: str
    source_name: str
    source_url: str
    source_key: str
    event_key: str


class _BoundedRssCollector(FrontierNewsService):
    """Reuse the existing RSS normalizer with bounded, fixed-host network reads."""

    async def _read_url(self, url: str) -> str:
        """Fetch one fixed configured feed with size, connection and total limits."""

        return await asyncio.wait_for(asyncio.to_thread(read_feed, url), timeout=TOTAL_TIMEOUT)


class ScheduledContentService:
    """Publish one fresh source-backed item per channel/slot as its managed owner."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Store the caller-owned session and settings; no credentials or I/O are used."""

        self.session = session
        self.settings = settings or get_settings()

    async def collect_hot_search(
        self, scheduled_for: datetime, *, persist: bool = True
    ) -> dict[str, object]:
        """Collect/reuse one immutable slot snapshot; persist only when requested.

        The timezone-aware slot must be 10:00, 14:00 or 18:00 Shanghai time.
        Existing same-slot files are reused on retries, never replaced by a later batch.
        """

        local, _ = slot_identity("hot_search", scheduled_for)
        output = weibo.DEFAULT_OUTPUT_DIR / local.date().isoformat() / f"{local.hour:02d}.json"
        if persist and output.exists():
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(snapshot, dict) or snapshot.get("scheduled_for") != local.isoformat():
                raise RuntimeError("微博热搜时段快照标识不匹配，停止以免覆盖已有数据")
            return snapshot
        snapshot = weibo.build_snapshot(
            await asyncio.wait_for(
                asyncio.to_thread(weibo.fetch_hot_search_payload, timeout=REQUEST_TIMEOUT),
                timeout=TOTAL_TIMEOUT,
            ),
            limit=20,
            include_ads=False,
        )
        snapshot["scheduled_for"] = local.isoformat()
        if persist:
            await asyncio.to_thread(weibo.write_snapshot, snapshot, output)
        return snapshot

    async def publish_slot(
        self,
        channel: ContentChannel,
        scheduled_for: datetime,
        *,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Publish at most one new source/event for one Shanghai slot.

        Network acquisition finishes before the fixed owner row is locked. Under
        that lock, slot/source/event audits are rechecked. Pending audits join the
        canonical create-topic transaction, so a crash after its internal commit
        cannot cause duplicate publication. No account is created or normalized.
        """

        local, slot_key = slot_identity(channel, scheduled_for)
        drafts, errors = await self._collect_drafts(channel, local, persist=not dry_run)
        if not drafts:
            return {
                "status": "no_candidate",
                "channel": channel,
                "slot": slot_key,
                "reason": "no_fresh_verified_source",
                "source_errors": errors,
            }
        try:
            author = await self._managed_author(channel, lock=not dry_run)
            previous = await self._audit(SLOT_ACTION, slot_key)
            if previous is not None:
                return await self._existing_result(previous, channel, slot_key)
            identity = IDENTITIES[channel]
            board = await self.session.scalar(
                select(Board).options(noload("*")).where(Board.slug == identity.board_slug)
            )
            if board is None or board.visibility != "public":
                raise ValidationError(
                    "scheduled_content_board_missing", "内容任务版块不存在或非公开"
                )
            # 新审计不覆盖历史发布器；一次读取有界公开首帖，防止首轮重发已存在的来源。
            recent = list(
                (
                    await self.session.execute(
                        select(Topic.title, Post.raw_md)
                        .join(Post, Post.topic_id == Topic.id)
                        .where(
                            Topic.board_id == board.id,
                            Topic.visibility == "public",
                            Topic.deleted_at.is_(None),
                            Post.post_number == 1,
                            Topic.created_at >= utcnow() - timedelta(hours=72),
                        )
                        .order_by(Topic.created_at.desc())
                        .limit(100)
                    )
                ).all()
            )
            # 海外合集按单条原帖去重；先筛掉历史内容，再组一篇，避免只新增一条却重发整组。
            overseas_sources = []
            if channel == "overseas":
                overseas_sources = await self._unpublished_overseas(drafts, recent)
                drafts = [overseas_digest(overseas_sources)] if overseas_sources else []
            for draft in drafts:
                if channel != "overseas":
                    if draft_matches_recent(draft, recent):
                        continue
                    if await self._audit(SOURCE_ACTION, draft.source_key) is not None:
                        continue
                    if await self._audit(EVENT_ACTION, draft.event_key) is not None:
                        continue
                if dry_run:
                    return {
                        "status": "preview",
                        "channel": channel,
                        "slot": slot_key,
                        "author": author.username,
                        "title": draft.title,
                        "source_url": draft.source_url,
                        "raw_md": draft.raw_md,
                        "source_errors": errors,
                    }
                # 审计先挂入同一事务；ForumService 的提交同时保存帖子与防重标识。
                created_at = utcnow()
                data: dict[str, object] = {
                    "channel": channel,
                    "slot": slot_key,
                    "title": draft.title,
                    "source_name": draft.source_name,
                    "source_url": draft.source_url,
                    "source_key": draft.source_key,
                    "event_key": draft.event_key,
                }
                # 时段回执和每条原帖标识同属发帖事务；崩溃恢复仍可沿第一条原帖找回合集。
                markers = [(SLOT_ACTION, slot_key, draft)]
                for item in overseas_sources or [draft]:
                    markers.extend((
                        (SOURCE_ACTION, item.source_key, item),
                        (EVENT_ACTION, item.event_key, item),
                    ))
                records = [
                    AuditLog(
                        actor_id=author.id,
                        action=action,
                        target_type=AUDIT_TARGET,
                        target_id=key,
                        board_id=board.id,
                        data={
                            **data,
                            "source_name": item.source_name,
                            "source_url": item.source_url,
                            "source_key": item.source_key,
                            "event_key": item.event_key,
                        },
                        created_at=created_at,
                    )
                    for action, key, item in markers
                ]
                for record in records:
                    self.session.add(record)
                topic = await ForumService(self.session).create_topic(
                    identity.board_slug,
                    TopicCreateRequest(
                        title=draft.title, raw_md=draft.raw_md, tags=list(identity.tags)
                    ),
                    author,
                    skip_spam_checks=True,
                    skip_review_queue=True,
                )
                for record in records:
                    record.data = {**record.data, "topic_id": topic.id, "title": topic.title}
                await self.session.commit()
                return {
                    "status": "published",
                    "channel": channel,
                    "slot": slot_key,
                    "topic_id": topic.id,
                    "title": topic.title,
                    "source_url": draft.source_url,
                    "source_errors": errors,
                }
            return {
                "status": "no_candidate",
                "channel": channel,
                "slot": slot_key,
                "reason": "all_sources_or_events_already_published",
                "source_errors": errors,
            }
        finally:
            # 预览、跳过及异常均释放专用身份行锁，不让网络重试持有数据库事务。
            await self.session.rollback()

    async def _unpublished_overseas(
        self, drafts: list[SourcedDraft], recent: list
    ) -> list[SourcedDraft]:
        """批量核对候选原帖/内容标识，返回最多五条未发内容；调用方已锁定专用账号。"""

        candidates = [draft for draft in drafts if not draft_matches_recent(draft, recent)]
        if not candidates:
            return []
        keys = {key for draft in candidates for key in (draft.source_key, draft.event_key)}
        rows = await self.session.execute(
            select(AuditLog.action, AuditLog.target_id)
            .where(
                AuditLog.target_type == AUDIT_TARGET,
                AuditLog.action.in_((SOURCE_ACTION, EVENT_ACTION)),
                AuditLog.target_id.in_(keys),
            )
            .distinct()
        )
        known = set(rows.all())
        selected = []
        for draft in candidates:
            markers = {(SOURCE_ACTION, draft.source_key), (EVENT_ACTION, draft.event_key)}
            if known.intersection(markers):
                continue
            known.update(markers)
            selected.append(draft)
            if len(selected) == overseas_content.MAX_DIGEST_ITEMS:
                break
        return selected

    async def _managed_author(self, channel: ContentChannel, *, lock: bool) -> User:
        """Return the exact active, non-admin seeded persona, optionally locking it."""

        identity = IDENTITIES[channel]
        statement = select(User).where(User.username == identity.username)
        if lock:
            statement = statement.with_for_update()
        author = await self.session.scalar(statement)
        expected_kind = seeded_persona_kind(identity.username, identity.email)
        if (
            author is None
            or author.email != identity.email
            or author.status != "active"
            or author.role != "user"
            or author.is_persona is not True
            or expected_kind is None
            or author.persona_kind != expected_kind
        ):
            raise PermissionDeniedError(
                "scheduled_content_identity_invalid", "专用发布身份未通过核对，内容任务已停止"
            )
        return author

    async def _audit(self, action: str, target_id: str) -> AuditLog | None:
        """Return one exact existing duplicate marker; no unbounded history scan is used."""

        return await self.session.scalar(
            select(AuditLog)
            .options(noload("*"))
            .where(
                AuditLog.action == action,
                AuditLog.target_type == AUDIT_TARGET,
                AuditLog.target_id == target_id,
            )
            .order_by(AuditLog.id.desc())
            .limit(1)
        )

    async def _existing_result(
        self, audit: AuditLog, channel: ContentChannel, slot_key: str
    ) -> dict[str, object]:
        """Recover a missing receipt from bounded author/board/time/source matching.

        The durable audit is authoritative even when its receipt cannot be found;
        an inconsistent receipt fails closed rather than publishing a second item.
        """

        topic_id = (audit.data or {}).get("topic_id")
        if not topic_id:
            source_url = str((audit.data or {}).get("source_url") or "")
            statement = (
                select(Topic)
                .options(noload("*"))
                .join(Post, Post.topic_id == Topic.id)
                .where(
                    Topic.user_id == audit.actor_id,
                    Topic.board_id == audit.board_id,
                    Topic.created_at >= audit.created_at,
                    Topic.created_at <= as_utc_datetime(audit.created_at) + timedelta(minutes=5),
                    Post.post_number == 1,
                    Post.raw_md.contains(source_url, autoescape=True),
                )
                .order_by(Topic.id)
                .limit(2)
            )
            matches = list(await self.session.scalars(statement)) if source_url else []
            if len(matches) != 1:
                raise ConflictError(
                    "scheduled_content_receipt_missing",
                    "发布审计已存在，帖子回执需人工核对；不重复发帖",
                )
            topic_id = matches[0].id
            audit.data = {**audit.data, "topic_id": topic_id}
            await self.session.commit()
        return {
            "status": "already_published",
            "channel": channel,
            "slot": slot_key,
            "topic_id": topic_id,
        }

    async def _collect_drafts(
        self, channel: ContentChannel, scheduled_for: datetime, *, persist: bool
    ) -> tuple[list[SourcedDraft], list[str]]:
        """Acquire bounded current candidates before opening any database transaction."""

        if channel == "hot_search":
            snapshot = await self.collect_hot_search(scheduled_for, persist=persist)
            draft = hot_search_draft(snapshot, scheduled_for)
            return ([draft] if draft is not None else []), []
        if channel == "overseas":
            # 只读固定公开账号，不调用登录、付费模型或旧资讯队列；采集完成后才进入发帖事务。
            entries, errors = await overseas_content.collect_entries(read_feed)
            return [overseas_draft(entry) for entry in entries], errors
        collector = _BoundedRssCollector(self.session, self.settings)
        drafts: list[SourcedDraft] = []
        errors: list[str] = []
        failures: list[Exception] = []
        for name, url, hosts in FEEDS[channel]:
            source = FrontierNewsSource(
                name=name,
                key=name,
                kind="rss",
                url=url,
                config={
                    "max_items": 20,
                    "keywords": list(AI_KEYWORDS) if channel == "news" else [],
                },
                trust_level=100,
                fetch_interval_minutes=60,
            )
            try:
                entries = await collector._fetch_rss_entries(source)
            except (OSError, ValueError, RuntimeError, TimeoutError, ET.ParseError) as exc:
                errors.append(f"{name}: {type(exc).__name__}")
                failures.append(exc)
                continue
            entries.sort(
                key=lambda entry: as_utc_datetime(
                    entry.published_at or datetime.min.replace(tzinfo=utcnow().tzinfo)
                ),
                reverse=True,
            )
            for entry in entries:
                draft = news_draft(channel, name, entry, hosts=hosts, now=utcnow())
                if draft is not None:
                    drafts.append(draft)
        if len(failures) == len(FEEDS[channel]):
            # 来源整体失效与确实没有新稿分开；只让暂态网络错误进入有界重试。
            retryable = any(
                isinstance(exc, OSError | TimeoutError)
                and (not isinstance(exc, HTTPError) or exc.code in (408, 429, 500, 502, 503, 504))
                for exc in failures
            )
            if retryable:
                raise OSError("scheduled_content_sources_temporarily_unavailable")
            raise ValidationError(
                "scheduled_content_sources_invalid", "全部资讯来源不可用，停止发布"
            )
        return drafts, errors


def slot_identity(channel: str, scheduled_for: datetime) -> tuple[datetime, str]:
    """Validate an aware scheduled slot and return its Shanghai datetime/stable key."""

    if channel not in IDENTITIES or scheduled_for.tzinfo is None:
        raise ValueError("内容频道无效或任务时间缺少时区")
    local = as_shanghai_datetime(scheduled_for)
    if local.hour not in {10, 14, 18} or local.minute or local.second or local.microsecond:
        raise ValueError("内容任务仅接受北京时间 10:00、14:00、18:00 时段")
    return local, f"{channel}:{local.date().isoformat()}:{local.hour:02d}"


def source_key(url: str) -> str:
    """Return a stable canonical-source identity for cross-slot publication deduplication."""

    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.lower().startswith("utm_")
        and k.lower() not in {"ocid", "ref", "at_medium", "at_campaign"}
    ]
    canonical = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(sorted(query)),
            "",
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def draft_matches_recent(draft: SourcedDraft, recent: list) -> bool:
    """按规范来源和标题事实指纹检查最多100条旧公开帖子，不把新审计当全部历史。"""

    for title, body in recent:
        event = re.sub(r"[\W_]+", "", str(title).split("｜", 1)[-1].casefold())
        if hashlib.sha256(event.encode()).hexdigest() == draft.event_key:
            return True
        for url in re.findall(r"https://[^\s<>\]\)]+", str(body)):
            if source_key(html.unescape(url)) == draft.source_key:
                return True
    return False


def news_draft(
    channel: ContentChannel,
    source_name: str,
    entry: FetchedNewsEntry,
    *,
    hosts: tuple[str, ...],
    now: datetime,
) -> SourcedDraft | None:
    """Build an attributed source card only for a recent, dated, allowed-host entry."""

    parts = urlsplit(entry.url)
    if parts.scheme != "https" or parts.hostname not in hosts or parts.username or parts.password:
        return None
    if entry.published_at is None or not entry.title.strip():
        return None
    age = as_utc_datetime(now) - as_utc_datetime(entry.published_at)
    if age < -timedelta(minutes=5) or age > MAX_NEWS_AGE:
        return None
    original_title = plain_text(entry.title, limit=400)
    title = f"{'体坛快讯' if channel == 'sports' else '资讯速递'}｜{original_title}"[:180]
    excerpt = plain_text(entry.summary or "", limit=180)
    published = as_shanghai_datetime(entry.published_at).isoformat(timespec="minutes")
    # 只引用来源已有摘要，不把榜单或模型推断扩写成事实。
    body = f"[{markdown_label(original_title)}]({entry.url})\n"
    if excerpt:
        body += f"\n来源短摘：{excerpt}\n"
    # 正文先呈现来源内容，来源时间与自动标识保留在末尾。
    body += f"\n来源：{source_name} · 原文时间：{published}\n\n> 自动整理，详见原文。\n"
    event = re.sub(r"[\W_]+", "", original_title.casefold())
    return SourcedDraft(
        title,
        body,
        source_name,
        entry.url,
        source_key(entry.url),
        hashlib.sha256(event.encode()).hexdigest(),
    )


def hot_search_draft(
    snapshot: Mapping[str, object], scheduled_for: datetime
) -> SourcedDraft | None:
    """Render a distinct ranked-list observation, never a claim that trends are true."""

    slot_identity("hot_search", scheduled_for)
    raw_topics = snapshot.get("topics")
    topics = (
        [
            item
            for item in raw_topics
            if isinstance(item, dict)
            and str(item.get("title", "")).strip()
            and urlsplit(str(item.get("url", ""))).hostname == "s.weibo.com"
            and str(item.get("url", "")).startswith("https://")
        ][:10]
        if isinstance(raw_topics, list)
        else []
    )
    if not topics:
        return None
    # 相同词条集合不因名次、热度、采集时间变化重复发；下批必须有真实榜单变化。
    normalized = sorted(
        {re.sub(r"[\W_]+", "", str(item.get("title", "")).casefold()) for item in topics}
    )
    normalized = [item for item in normalized if item]
    if not normalized:
        return None
    digest = hashlib.sha256("\n".join(normalized).encode()).hexdigest()
    title = weibo.hot_search_title(topics)
    body = ""
    for item in topics[:10]:
        url = str(item.get("url") or "")
        if urlsplit(url).hostname != "s.weibo.com" or not url.startswith("https://"):
            continue
        body += f"{item.get('rank', '')}. [{markdown_label(str(item.get('title') or ''))}]({url})\n"
    # 标题只展示榜单词条，采集时间和必要提示移至末尾，避免占满列表摘要。
    body += (
        f"\n采集时间：{snapshot.get('collected_at', '')}\n\n"
        "来源：[微博热搜榜](https://s.weibo.com/top/summary)\n\n"
        f"{weibo.HOT_SEARCH_AUTOMATION_MARKER}\n"
    )
    return SourcedDraft(
        title,
        body,
        "微博热搜榜",
        "https://s.weibo.com/top/summary",
        f"weibo:{digest}",
        f"weibo:{digest}",
    )


def plain_text(value: str, *, limit: int) -> str:
    """Strip source markup and limit short quotations; never synthesize missing facts."""

    clean = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
    if len(clean.split()) > 25:
        clean = " ".join(clean.split()[:25])
    return clean[:limit]


def markdown_label(value: str) -> str:
    """Escape source labels so feed text cannot inject Markdown links or emphasis."""

    return re.sub(r"([\\`*{}\[\]()#+.!_>])", r"\\\1", value.replace("\n", " "))


def overseas_draft(entry: overseas_content.SocialEntry) -> SourcedDraft:
    """将已验证的公开原帖转为带作者、平台、时间及短摘的候选，不翻译或扩写原文。"""

    # 复用圈子小型渲染器的150字链接标签；它不支持反斜杠转义，且超过160字不会识别链接。
    excerpt = frontier_markdown_label(plain_text(entry.text, limit=180))
    published = as_shanghai_datetime(entry.published_at).isoformat(timespec="minutes")
    body = (
        f"[{excerpt}]({entry.url})\n\n"
        f"来源：{frontier_markdown_label(entry.source_name)} · "
        f"{frontier_markdown_label(entry.author)}"
        f" · 原文时间：{published}\n"
    )
    event = re.sub(r"[\W_]+", "", entry.text.casefold())
    # 同一出版者同步到两个平台时按文章外链防重；无文章外链的原创动态按原文指纹防重。
    event_key = (
        source_key(entry.article_url) if entry.article_url
        else hashlib.sha256(event.encode()).hexdigest()
    )
    return SourcedDraft(
        excerpt, body, entry.source_name, entry.url, source_key(entry.url),
        event_key,
    )


def overseas_digest(items: list[SourcedDraft]) -> SourcedDraft:
    """把一至五条已去重原帖组成单篇合集；不补旧稿，原文短摘不表示事实核实。"""

    if not 1 <= len(items) <= overseas_content.MAX_DIGEST_ITEMS:
        raise ValueError("海外合集条数无效")
    # 英文/德文标题在词边界缩略，避免直接截断后留下半个单词。
    headlines = []
    for item in items[:2]:
        headline = item.title
        if len(headline) > 70:
            headline = headline[:70]
            headline = headline.rsplit(" ", 1)[0] if " " in headline else headline
            headline += "…"
        headlines.append(headline)
    title = "海外动态｜" + "、".join(headlines)
    body = "\n".join(f"{index}. {item.raw_md}" for index, item in enumerate(items, 1))
    body += "\n自动收集公开动态，保留原文短摘；观点与消息未经本站独立核实，详见原帖。\n"
    joined_keys = "|".join(sorted(item.source_key for item in items))
    digest = hashlib.sha256(joined_keys.encode()).hexdigest()
    return SourcedDraft(
        title[:180], body, "Bluesky / Mastodon 公开动态", items[0].source_url,
        f"overseas:{digest}", f"overseas:{digest}",
    )


def read_feed(url: str) -> str:
    """Read only configured feeds with bounded size/time and no arbitrary redirects."""

    configured = {feed_url for feeds in FEEDS.values() for _, feed_url, _ in feeds}
    social_urls = {source.url for source in overseas_content.SOURCES}
    configured.update(social_urls)
    if url not in configured:
        raise ValueError("未批准的资讯采集地址")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        """Reject redirects rather than following a feed to an unapproved host."""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": weibo.USER_AGENT,
            "Accept": (
                "application/json" if url in social_urls
                else "application/rss+xml, application/xml, text/xml"
            ),
        },
    )
    started = time.monotonic()
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=REQUEST_TIMEOUT
    ) as response:
        chunks: list[bytes] = []
        size = 0
        while True:
            if time.monotonic() - started > TOTAL_TIMEOUT - REQUEST_TIMEOUT:
                raise TimeoutError("资讯采集超过总时限")
            chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ValueError("资讯来源响应过大")
            chunks.append(chunk)
        encoding = response.headers.get_content_charset() or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")
