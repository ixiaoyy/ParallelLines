from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import structlog
from redis import asyncio as redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import AppError, ValidationError
from app.schemas.workspace import HotListItem, HotListSnapshot

_LOGGER = structlog.get_logger(__name__)

HOT_LIST_CACHE_PREFIX = "parallellines:workspace:hot_list:v1:"
FRESH_TTL_SECONDS = 300
STALE_TTL_SECONDS = 3600
UPSTREAM_TIMEOUT_SECONDS = 4.5
MAX_ITEMS = 20

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class HotSourceSpec:
    id: str
    label: str
    site_url: str


HOT_SOURCES: dict[str, HotSourceSpec] = {
    "weibo": HotSourceSpec(
        id="weibo",
        label="微博热搜",
        site_url="https://s.weibo.com/top/summary",
    ),
    "baidu": HotSourceSpec(
        id="baidu",
        label="百度热搜",
        site_url="https://top.baidu.com/board?tab=realtime",
    ),
    "bilibili": HotSourceSpec(
        id="bilibili",
        label="B站热门",
        site_url="https://www.bilibili.com/v/popular/all",
    ),
    "hackernews": HotSourceSpec(
        id="hackernews",
        label="Hacker News",
        site_url="https://news.ycombinator.com/",
    ),
}

_MEMORY_CACHE: dict[str, tuple[float, HotListSnapshot]] = {}
_SOURCE_LOCKS: dict[str, asyncio.Lock] = {}


def _get_lock(source: str) -> asyncio.Lock:
    lock = _SOURCE_LOCKS.get(source)
    if lock is None:
        lock = asyncio.Lock()
        _SOURCE_LOCKS[source] = lock
    return lock


def _safe_http_url(url: object, fallback: str) -> str:
    if not isinstance(url, str):
        return fallback
    cleaned = url.strip()
    if not cleaned:
        return fallback
    try:
        parsed = urlsplit(cleaned)
    except ValueError:
        return fallback
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        return cleaned
    return fallback


def _format_cn_count(value: object, suffix: str = "") -> str:
    try:
        num = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if num <= 0:
        return ""
    if num >= 100_000_000:
        return f"{num / 100_000_000:.1f}亿{suffix}"
    if num >= 10_000:
        return f"{num / 10_000:.1f}万{suffix}"
    return f"{num}{suffix}"


def _clean_text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _parse_weibo(payload: dict[str, Any], spec: HotSourceSpec) -> list[HotListItem]:
    realtime = (payload.get("data") or {}).get("realtime") or []
    items: list[HotListItem] = []
    for entry in realtime:
        if not isinstance(entry, dict) or entry.get("is_ad") == 1 or entry.get("is_gov") == 1:
            continue
        title = _clean_text(entry.get("word") or entry.get("note"), 120)
        if not title:
            continue
        raw_word = str(entry.get("word_scheme") or f"#{title}#")
        url = f"https://s.weibo.com/weibo?q={quote(raw_word, safe='')}"
        tag = _clean_text(entry.get("label_name") or entry.get("icon_desc"), 8)
        hot_value = _format_cn_count(entry.get("num"))
        items.append(
            HotListItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot_value=hot_value,
                tag=tag,
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


def _parse_baidu(payload: dict[str, Any], spec: HotSourceSpec) -> list[HotListItem]:
    cards = (payload.get("data") or {}).get("cards") or []
    raw_entries: list[Any] = []
    if cards and isinstance(cards[0], dict):
        content = cards[0].get("content") or []
        if content and isinstance(content[0], dict) and isinstance(content[0].get("content"), list):
            raw_entries = content[0]["content"]
        elif isinstance(content, list):
            raw_entries = content

    tag_map = {"1": "新", "3": "热", "4": "沸"}
    items: list[HotListItem] = []
    for entry in raw_entries:
        if not isinstance(entry, dict) or entry.get("isTop"):
            continue
        hot_tag = str(entry.get("hotTag") or "")
        if hot_tag == "2":  # 商业推广项跳过
            continue
        title = _clean_text(entry.get("word") or entry.get("query"), 120)
        if not title:
            continue
        fallback_url = f"https://www.baidu.com/s?wd={quote(title, safe='')}"
        raw_url = entry.get("appUrl") or entry.get("rawUrl") or entry.get("url")
        url = _safe_http_url(raw_url, fallback_url)
        hot_value = _format_cn_count(entry.get("hotScore"))
        items.append(
            HotListItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot_value=hot_value,
                tag=tag_map.get(hot_tag, ""),
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


def _parse_bilibili(payload: dict[str, Any], spec: HotSourceSpec) -> list[HotListItem]:
    entries = (payload.get("data") or {}).get("list") or []
    items: list[HotListItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = _clean_text(entry.get("title"), 120)
        if not title:
            continue
        bvid = _clean_text(entry.get("bvid"), 32)
        fallback_url = f"https://www.bilibili.com/video/{bvid}" if bvid else spec.site_url
        url = _safe_http_url(entry.get("short_link_v2"), fallback_url)
        stat = entry.get("stat") if isinstance(entry.get("stat"), dict) else {}
        hot_value = _format_cn_count(stat.get("view"), "播放")
        rcmd = entry.get("rcmd_reason") if isinstance(entry.get("rcmd_reason"), dict) else {}
        tag = _clean_text(rcmd.get("content"), 10)
        items.append(
            HotListItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot_value=hot_value,
                tag=tag,
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


def _parse_hackernews(payload: dict[str, Any], spec: HotSourceSpec) -> list[HotListItem]:
    hits = payload.get("hits") or []
    items: list[HotListItem] = []
    for entry in hits:
        if not isinstance(entry, dict):
            continue
        title = _clean_text(entry.get("title"), 120)
        if not title:
            continue
        object_id = _clean_text(entry.get("objectID"), 32)
        fallback_url = (
            f"https://news.ycombinator.com/item?id={object_id}" if object_id else spec.site_url
        )
        url = _safe_http_url(entry.get("url"), fallback_url)
        points = entry.get("points")
        hot_value = f"{points} pts" if isinstance(points, int) and points > 0 else ""
        items.append(
            HotListItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot_value=hot_value,
                tag="",
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


async def _fetch_upstream(source: str, spec: HotSourceSpec) -> list[HotListItem]:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json, text/plain, */*"}
    if source == "weibo":
        url = "https://weibo.com/ajax/side/hotSearch"
        headers["Referer"] = "https://weibo.com/"
        parser = _parse_weibo
    elif source == "baidu":
        url = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
        headers["Referer"] = "https://top.baidu.com/"
        parser = _parse_baidu
    elif source == "bilibili":
        url = "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1"
        headers["Referer"] = "https://www.bilibili.com/"
        parser = _parse_bilibili
    elif source == "hackernews":
        url = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=20"
        parser = _parse_hackernews
    else:
        raise ValidationError("unsupported_hot_source", "不支持的热榜来源")

    async with httpx.AsyncClient(
        timeout=UPSTREAM_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers=headers,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid upstream payload")
    items = parser(payload, spec)
    if not items:
        raise ValueError("Empty hot list response")
    return items


async def _read_redis_snapshot(
    settings: Settings, source: str
) -> tuple[float, HotListSnapshot] | None:
    if not settings.redis_url:
        return None
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = await client.get(f"{HOT_LIST_CACHE_PREFIX}{source}")
        if not raw:
            return None
        parsed = json.loads(raw)
        fetched_at = float(parsed["fetched_at"])
        snapshot = HotListSnapshot.model_validate(parsed["snapshot"])
        return fetched_at, snapshot
    except (RedisError, ValueError, KeyError, TypeError):
        return None
    finally:
        await client.aclose()


async def _write_redis_snapshot(
    settings: Settings, source: str, fetched_at: float, snapshot: HotListSnapshot
) -> None:
    if not settings.redis_url:
        return
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        envelope = json.dumps(
            {"fetched_at": fetched_at, "snapshot": snapshot.model_dump(mode="json")},
            ensure_ascii=False,
        )
        await client.set(f"{HOT_LIST_CACHE_PREFIX}{source}", envelope, ex=STALE_TTL_SECONDS)
    except RedisError:
        pass
    finally:
        await client.aclose()


async def get_hot_list_snapshot(
    settings: Settings, source: str, *, force_refresh: bool = False
) -> HotListSnapshot:
    normalized = source.strip().lower()
    spec = HOT_SOURCES.get(normalized)
    if spec is None:
        raise ValidationError("unsupported_hot_source", "不支持的热榜来源")

    now = time.time()
    cached = _MEMORY_CACHE.get(normalized)
    if cached and not force_refresh and (now - cached[0]) < FRESH_TTL_SECONDS:
        return cached[1]

    async with _get_lock(normalized):
        now = time.time()
        cached = _MEMORY_CACHE.get(normalized)
        if cached and not force_refresh and (now - cached[0]) < FRESH_TTL_SECONDS:
            return cached[1]

        redis_cached = await _read_redis_snapshot(settings, normalized)
        if redis_cached and not force_refresh and (now - redis_cached[0]) < FRESH_TTL_SECONDS:
            _MEMORY_CACHE[normalized] = redis_cached
            return redis_cached[1]

        stale_candidate = cached or redis_cached
        try:
            items = await _fetch_upstream(normalized, spec)
            snapshot = HotListSnapshot(
                source=spec.id,
                label=spec.label,
                site_url=spec.site_url,
                updated_at=datetime.now(UTC),
                stale=False,
                items=items,
            )
            _MEMORY_CACHE[normalized] = (now, snapshot)
            await _write_redis_snapshot(settings, normalized, now, snapshot)
            return snapshot
        except Exception as exc:
            _LOGGER.warning(
                "workspace_hot_list_fetch_failed",
                source=normalized,
                error_type=type(exc).__name__,
            )
            if stale_candidate is not None:
                return stale_candidate[1].model_copy(update={"stale": True})
            raise AppError(
                "hot_list_unavailable",
                f"暂时无法获取{spec.label}，请稍后重试或直接访问原站",
                status_code=503,
            ) from None
