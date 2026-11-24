from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel
from redis import asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError, ResponseError

from app.core.config import Settings
from app.core.exceptions import AppError, PermissionDeniedError, ValidationError
from app.core.visitors import VISITOR_ID_PATTERN
from app.db.base import as_utc_datetime, utcnow
from app.schemas.traffic import TrafficBatchRequest, TrafficIdentityScope, TrafficQueueStatus
from app.services.site_visits import (
    SEARCH_HOST_MARKERS,
    SOCIAL_HOST_MARKERS,
    is_probable_bot_user_agent,
)

TRAFFIC_STREAM = "parallellines:traffic:v1:events"
TRAFFIC_GROUP = "traffic-writers"
TRAFFIC_META = "parallellines:traffic:v1:meta"
TRAFFIC_REPORT_PREFIX = "parallellines:traffic:v1:report:"
SITE_NAMES = {"games": "游戏", "forum": "圈子", "tools": "工具", "chat": "Chat", "api": "模型网关"}
HOST_SITES: dict[str, set[str]] = {
    "pingxingxian.space": {"games", "forum", "tools"},
    "www.pingxingxian.space": {"games", "forum", "tools"},
    "forum.pingxingxian.space": {"forum"},
    "tools.pingxingxian.space": {"tools"},
    "chat.pingxingxian.space": {"chat"},
    "api.pingxingxian.space": {"api"},
}

# 容量检查和追加在同一 Redis 脚本内完成；满载拒收，不裁掉尚未提交的事件。
ENQUEUE_SCRIPT = """
local count = #ARGV - 3
local pending = redis.call('XLEN', KEYS[1])
if pending + count > tonumber(ARGV[1]) then
  redis.call('HINCRBY', KEYS[2], 'dropped_events', count)
  return -1
end
local rate = redis.call('INCRBY', KEYS[3], count)
if rate == count then redis.call('EXPIRE', KEYS[3], 60) end
if rate > 120 then
  redis.call('HINCRBY', KEYS[2], 'dropped_events', count)
  return -2
end
for i = 4, #ARGV do
  redis.call('XADD', KEYS[1], '*', 'data', ARGV[i])
end
redis.call('HSET', KEYS[2], 'last_accepted_at', ARGV[2])
return count
"""


class QueuedTrafficEvent(BaseModel):
    event_id: str
    site_key: str
    visitor_key: str
    identity_scope: TrafficIdentityScope
    event_name: str
    path: str
    source_type: str
    source_name: str
    occurred_at: datetime
    received_at: datetime


@lru_cache(maxsize=4)
def traffic_redis(url: str, timeout: float) -> redis.Redis:
    """复用统计专用小连接池；参数为地址和秒级超时，返回异步客户端，不连接数据库。"""

    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        max_connections=4,
        retry_on_timeout=False,
        retry=Retry(NoBackoff(), 0),
    )


def validate_traffic_origin(origin: str | None, site_keys: set[str], settings: Settings) -> str:
    """验证来源与站点对应关系；仅显式开发开关允许回环地址，返回归一化来源。"""

    try:
        parsed = urlsplit(origin or "")
        port = parsed.port
    except ValueError as exc:
        raise PermissionDeniedError("traffic_origin_denied", "统计来源无效") from exc
    host = (parsed.hostname or "").lower()
    if (
        parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise PermissionDeniedError("traffic_origin_denied", "统计来源不受信任")
    allowed = (
        HOST_SITES.get(host, set()) if parsed.scheme == "https" and port in {None, 443} else set()
    )
    if settings.traffic_allow_loopback and host in {"localhost", "127.0.0.1", "::1"}:
        if parsed.scheme in {"http", "https"}:
            allowed = set(SITE_NAMES)
    if not site_keys or not site_keys.issubset(allowed):
        raise PermissionDeniedError("traffic_origin_denied", "统计站点与来源不匹配")
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_traffic_path(raw: str, site_key: str) -> str | None:
    """移除查询和片段并归一化私密动态地址；返回可存储路径，排除管理和认证页。"""

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    path = unquote(parsed.path).split("?", 1)[0].split("#", 1)[0]
    if parsed.scheme or parsed.netloc or not path.startswith("/") or path.startswith("//"):
        return None
    if any(ord(char) < 32 for char in path) or any(char in path for char in '<>"\\'):
        return None
    if re.match(
        r"^/(?:admin|auth|account|messages|oauth|oauth2|login|register|signin|signup)(?:/|$)",
        path,
        re.IGNORECASE,
    ):
        return None
    if site_key == "chat":
        if re.match(r"^/(?:c|t|s)/", path):
            path = f"/{path.split('/')[1]}/:chat"
        elif path.startswith("/workspace/"):
            path = "/workspace/:section"
    path = re.sub(r"^/(members|users|space)/[^/]+.*$", r"/\1/:member", path)
    return path[:256]


def _source(referrer: str | None, campaign: str | None) -> tuple[str, str]:
    """按来源主机或已校验投放标记分类，不保存来源路径和参数。"""

    if campaign:
        return "campaign", campaign
    try:
        host = (urlsplit(referrer or "").hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ValidationError("traffic_referrer_invalid", "统计来源格式无效") from exc
    if not host:
        return "direct", "Direct"
    if host in HOST_SITES:
        return "internal", host
    if any(marker in host for marker in SEARCH_HOST_MARKERS):
        return "search", host[:128]
    if any(marker in host for marker in SOCIAL_HOST_MARKERS):
        return "social", host[:128]
    return "referral", host[:128]


def normalize_traffic_batch(
    payload: TrafficBatchRequest,
    *,
    origin: str | None,
    user_agent: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[str, list[QueuedTrafficEvent]]:
    """校验批次并产生隐私化队列事件；不查业务数据库，也不保存原始访客标识。"""

    normalized_origin = validate_traffic_origin(
        origin, {event.site_key for event in payload.events}, settings
    )
    if not VISITOR_ID_PATTERN.fullmatch(payload.visitor_id):
        raise ValidationError("traffic_visitor_invalid", "统计访客标识无效")
    if is_probable_bot_user_agent(user_agent):
        return normalized_origin, []
    received_at = as_utc_datetime(now or utcnow())
    events = []
    for item in payload.events:
        if item.occurred_at.tzinfo is None:
            raise ValidationError("traffic_time_invalid", "统计时间必须包含时区")
        occurred_at = item.occurred_at.astimezone(UTC)
        if (
            not received_at - timedelta(hours=24)
            <= occurred_at
            <= received_at + timedelta(minutes=5)
        ):
            raise ValidationError("traffic_time_invalid", "统计时间超出接收窗口")
        path = normalize_traffic_path(item.path, item.site_key)
        if path is None:
            continue
        # 非共享身份按站点加盐，不能让相同的站内/临时 ID 冒充跨站访客。
        salt = "shared" if payload.identity_scope == "shared" else item.site_key
        digest = sha256(f"{salt}:{payload.visitor_id}".encode()).hexdigest()
        source_type, source_name = _source(item.referrer, item.campaign_source)
        events.append(
            QueuedTrafficEvent(
                event_id=str(item.event_id),
                site_key=item.site_key,
                visitor_key=f"{payload.identity_scope}:{digest}",
                identity_scope=payload.identity_scope,
                event_name=item.event_name,
                path=path,
                source_type=source_type,
                source_name=source_name,
                occurred_at=occurred_at,
                received_at=received_at,
            )
        )
    return normalized_origin, events


class TrafficQueue:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        """绑定统计配置与可注入 Redis 客户端；构造时不进行网络操作。"""

        self.settings = settings
        self.client = client or traffic_redis(
            settings.redis_url, settings.traffic_redis_timeout_seconds
        )

    async def enqueue(self, events: list[QueuedTrafficEvent]) -> int:
        """原子追加有上限批次；返回接收数，满载/限流/连接失败明确拒收，不同步写 SQL。"""

        if not events:
            return 0
        visitor = events[0].visitor_key
        try:
            async with asyncio.timeout(self.settings.traffic_redis_timeout_seconds * 2):
                result = int(
                    await self.client.eval(
                        ENQUEUE_SCRIPT,
                        3,
                        TRAFFIC_STREAM,
                        TRAFFIC_META,
                        f"parallellines:traffic:v1:rate:{visitor}",
                        self.settings.traffic_queue_capacity,
                        events[0].received_at.isoformat(),
                        visitor,
                        *(event.model_dump_json() for event in events),
                    )
                )
        except (RedisError, OSError, TimeoutError) as exc:
            raise AppError(
                "traffic_queue_unavailable", "统计队列暂不可用", status_code=503
            ) from exc
        if result < 0:
            raise AppError(
                "traffic_queue_full" if result == -1 else "traffic_rate_limited",
                "统计队列已满" if result == -1 else "统计采集频率超限",
                status_code=429,
            )
        return result

    async def status(self) -> TrafficQueueStatus:
        """读取队列长度及拒收计数；失败返回不可用状态，不将未知值伪装成零。"""

        if not self.settings.traffic_enabled:
            return TrafficQueueStatus(status="disabled")
        try:
            pending = int(await self.client.xlen(TRAFFIC_STREAM))
            dropped = int(await self.client.hget(TRAFFIC_META, "dropped_events") or 0)
            return TrafficQueueStatus(
                status="full" if pending >= self.settings.traffic_queue_capacity else "ok",
                pending=pending,
                dropped_events=dropped,
            )
        except (RedisError, OSError):
            return TrafficQueueStatus(status="unavailable")

    async def claim(self, consumer: str) -> list[tuple[str, QueuedTrafficEvent]]:
        """恢复至少闲置60秒的未确认批次，再读取新事件；不阻塞，单次总数受批量上限约束。"""

        try:
            await self.client.xgroup_create(TRAFFIC_STREAM, TRAFFIC_GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        reclaimed = await self.client.xautoclaim(
            TRAFFIC_STREAM,
            TRAFFIC_GROUP,
            consumer,
            min_idle_time=60000,
            start_id="0-0",
            count=self.settings.traffic_batch_size,
        )
        messages = list(reclaimed[1])
        remaining = self.settings.traffic_batch_size - len(messages)
        if remaining:
            fresh = await self.client.xreadgroup(
                TRAFFIC_GROUP, consumer, {TRAFFIC_STREAM: ">"}, count=remaining
            )
            for _stream, rows in fresh:
                messages.extend(rows)
        return [
            (event_id, QueuedTrafficEvent.model_validate_json(data["data"]))
            for event_id, data in messages
        ]

    async def acknowledge(self, ids: list[str]) -> None:
        """只在 SQL 提交后确认并删除流条目，保留未提交数据供重启恢复。"""

        if ids:
            transaction = self.client.pipeline(transaction=True)
            transaction.xack(TRAFFIC_STREAM, TRAFFIC_GROUP, *ids)
            transaction.xdel(TRAFFIC_STREAM, *ids)
            await transaction.execute()
