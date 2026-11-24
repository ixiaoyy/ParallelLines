"""固定海外公开账号的只读采集；不使用凭据、付费接口、数据库或模型。"""

from __future__ import annotations

import asyncio
import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Literal
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit

from app.core.exceptions import ValidationError
from app.db.base import as_utc_datetime, utcnow

MAX_SOURCE_ITEMS = 5
MAX_DIGEST_ITEMS = 5
TOTAL_TIMEOUT = 25.0
MAX_AGE = timedelta(hours=48)


@dataclass(frozen=True)
class SocialSource:
    """固定来源地址、平台账号标识及所属原站；账号改名/迁移需重新核对配置。"""

    name: str
    platform: Literal["bluesky", "mastodon"]
    url: str
    actor_id: str
    handle: str
    profile_url: str
    article_hosts: tuple[str, ...]


# 账号由原站链接交叉核对；只读这四个端点，不跟随返回内容或重定向追加抓取。
SOURCES = (
    SocialSource(
        "Bluesky · Guardian US",
        "bluesky",
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
        "?actor=us.theguardian.com&limit=5",
        "did:plc:nl32untxngcg74dl3w7scd74",
        "us.theguardian.com",
        "https://bsky.app/profile/us.theguardian.com",
        ("www.theguardian.com", "theguardian.com"),
    ),
    SocialSource(
        "Bluesky · GamingOnLinux",
        "bluesky",
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
        "?actor=gamingonlinux.com&limit=5",
        "did:plc:m5dcinlrpxq6rm2uficksxp7",
        "gamingonlinux.com",
        "https://bsky.app/profile/gamingonlinux.com",
        ("www.gamingonlinux.com", "gamingonlinux.com"),
    ),
    SocialSource(
        "Mastodon · GamingOnLinux",
        "mastodon",
        "https://mastodon.social/api/v1/accounts/10947/statuses"
        "?limit=5&exclude_replies=true&exclude_reblogs=true",
        "10947",
        "gamingonlinux",
        "https://mastodon.social/@gamingonlinux",
        ("www.gamingonlinux.com", "gamingonlinux.com"),
    ),
    SocialSource(
        "Mastodon · heise online",
        "mastodon",
        "https://social.heise.de/api/v1/accounts/109720732052060290/statuses"
        "?limit=5&exclude_replies=true&exclude_reblogs=true",
        "109720732052060290",
        "heiseonline",
        "https://social.heise.de/@heiseonline",
        ("www.heise.de", "heise.de"),
    ),
)


@dataclass(frozen=True)
class SocialEntry:
    """已验证归属、公开性与时效的原帖；文章外链只用于防止跨平台重复，不抓取正文。"""

    source_name: str
    author: str
    text: str
    url: str
    published_at: datetime
    article_url: str | None


class _PostHtml(HTMLParser):
    """提取 Mastodon 正文文本和已有链接；不渲染 HTML，也不访问媒体。"""

    def __init__(self) -> None:
        """初始化单篇原帖的文本与链接列表，无外部副作用。"""

        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """保留段落边界及锚点地址，其他标签不进入最终内容。"""

        if tag in {"p", "br", "div"}:
            self.text.append(" ")
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)

    def handle_data(self, data: str) -> None:
        """收集标签之间的原文，随后统一压缩空白。"""

        self.text.append(data)


def _article_url(source: SocialSource, candidates: list[object]) -> str | None:
    """只接受所属出版站的 HTTPS 文章链接作跨平台去重键，不把主页/任意外链当事件。"""

    for value in candidates:
        if not isinstance(value, str) or any(char.isspace() for char in value):
            continue
        try:
            parts = urlsplit(value)
            port = parts.port
        except ValueError:
            continue
        if (
            parts.scheme == "https"
            and parts.hostname in source.article_hosts
            and not parts.username
            and not parts.password
            and port in (None, 443)
            and parts.path.strip("/")
        ):
            # 同一出版站的 www/非www 地址统一为配置中的首个域名，再交由发布层去除追踪参数。
            return urlunsplit(("https", source.article_hosts[0], parts.path, parts.query, ""))
    return None


def _published(value: object, now: datetime) -> datetime | None:
    """解析带时区的原帖时间；拒绝缺失、无时区、超过48小时或明显晚于当前时间的记录。"""

    if not isinstance(value, str):
        return None
    try:
        published = datetime.fromisoformat(value)
    except ValueError:
        return None
    if published.tzinfo is None or published.utcoffset() is None:
        return None
    age = as_utc_datetime(now) - as_utc_datetime(published)
    return published if -timedelta(minutes=5) <= age <= MAX_AGE else None


def parse_entries(source: SocialSource, payload: object, *, now: datetime) -> list[SocialEntry]:
    """规范化单个固定账号响应，最多五条；仅收公开原创，跳过敏感、回复及引用/转发。"""

    rows = (
        payload.get("feed")
        if source.platform == "bluesky" and isinstance(payload, dict)
        else payload
    )
    if not isinstance(rows, list):
        raise ValueError("overseas_content_invalid_response")
    entries = []
    for row in rows[:MAX_SOURCE_ITEMS]:
        if not isinstance(row, dict):
            continue
        if source.platform == "bluesky":
            post = row.get("post")
            if not isinstance(post, dict) or row.get("reason"):
                continue
            author, record = post.get("author"), post.get("record")
            if not isinstance(author, dict) or not isinstance(record, dict):
                continue
            if author.get("did") != source.actor_id or author.get("handle") != source.handle:
                raise ValueError("overseas_content_author_changed")
            # 标签涵盖平台/作者的敏感标记；引用帖可能包含另一个未审核主体，首批一并排除。
            embed = post.get("embed") or {}
            if (
                record.get("$type") != "app.bsky.feed.post"
                or record.get("reply")
                or record.get("labels")
                or post.get("labels")
                or author.get("labels")
                or not isinstance(embed, dict)
                or "record" in str(embed.get("$type", ""))
            ):
                continue
            match = re.fullmatch(
                rf"at://{re.escape(source.actor_id)}/app\.bsky\.feed\.post/([A-Za-z0-9._~-]+)",
                str(post.get("uri", "")),
            )
            if match is None:
                continue
            text = record.get("text")
            published = _published(record.get("createdAt"), now)
            url = f"https://bsky.app/profile/{source.actor_id}/post/{match[1]}"
            external = embed.get("external")
            links = [external.get("uri")] if isinstance(external, dict) else []
            # 只有富文本链接而没有外链卡片的合法帖子，也须与另一平台的同篇文章去重。
            facets = record.get("facets")
            if isinstance(facets, list):
                for facet in facets:
                    features = facet.get("features") if isinstance(facet, dict) else None
                    if isinstance(features, list):
                        links.extend(
                            feature.get("uri")
                            for feature in features
                            if isinstance(feature, dict)
                            and feature.get("$type") == "app.bsky.richtext.facet#link"
                        )
            article = _article_url(source, links)
        else:
            account = row.get("account")
            if not isinstance(account, dict):
                continue
            if account.get("id") != source.actor_id or account.get("acct") != source.handle:
                raise ValueError("overseas_content_author_changed")
            if (
                row.get("visibility") != "public"
                or row.get("sensitive") is not False
                or row.get("spoiler_text") != ""
                or row.get("in_reply_to_id")
                or row.get("reblog")
                or row.get("quote")
            ):
                continue
            status_id, markup = row.get("id"), row.get("content")
            if (
                not isinstance(status_id, str)
                or not status_id.isdecimal()
                or not isinstance(markup, str)
            ):
                continue
            url = f"{source.profile_url}/{status_id}"
            if row.get("url") != url:
                continue
            parser = _PostHtml()
            parser.feed(markup)
            text = "".join(parser.text)
            published = _published(row.get("created_at"), now)
            card = row.get("card")
            links = [card.get("url")] if isinstance(card, dict) else []
            article = _article_url(source, links + parser.links)
        if published is None or not isinstance(text, str) or not text.strip():
            continue
        entries.append(
            SocialEntry(
                source.name,
                f"@{source.handle}",
                " ".join(html.unescape(text).split()),
                url,
                published,
                article,
            )
        )
    return sorted(entries, key=lambda entry: as_utc_datetime(entry.published_at), reverse=True)


async def collect_entries(
    read_url: Callable[[str], str], *, now: datetime | None = None
) -> tuple[list[SocialEntry], list[str]]:
    """并行只读四个固定来源，单请求总限25秒；返回轮流取样的候选和稳定错误摘要。"""

    current = now or utcnow()
    results = await asyncio.gather(
        *(
            asyncio.wait_for(asyncio.to_thread(read_url, source.url), timeout=TOTAL_TIMEOUT)
            for source in SOURCES
        ),
        return_exceptions=True,
    )
    batches: list[list[SocialEntry]] = []
    failures: list[Exception] = []
    errors = []
    for source, result in zip(SOURCES, results, strict=True):
        try:
            if isinstance(result, BaseException):
                raise result
            batches.append(parse_entries(source, json.loads(result), now=current))
        except (OSError, ValueError, TimeoutError) as exc:
            failures.append(exc)
            errors.append(f"{source.name}: {type(exc).__name__}")
    if len(failures) == len(SOURCES):
        # 完全断源是失败，健康但无新帖才是正常跳过；暂态错误交给现有三次有界重试。
        retryable = any(
            isinstance(exc, OSError | TimeoutError)
            and (not isinstance(exc, HTTPError) or exc.code in (408, 429, 500, 502, 503, 504))
            for exc in failures
        )
        if retryable:
            raise OSError("overseas_content_sources_temporarily_unavailable")
        raise ValidationError(
            "overseas_content_sources_invalid", "海外动态来源全部不可用，停止发布"
        )
    # 轮流取各账号的新帖，避免最先配置或最活跃的账号独占一篇合集。
    entries = [
        batch[index] for index in range(MAX_SOURCE_ITEMS) for batch in batches if len(batch) > index
    ]
    return entries, errors
