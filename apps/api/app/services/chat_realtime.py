from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from typing import Literal
from uuid import uuid4

import structlog
from redis import asyncio as redis

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatMessageResponse, ChatPresenceResponse, ChatStreamResponse

logger = structlog.get_logger("chat.realtime")

ChatRealtimeEventType = Literal["message", "presence"]


@dataclass(frozen=True, slots=True)
class ChatRealtimeEvent:
    channel_id: str
    event_type: ChatRealtimeEventType
    payload_json: str
    last_message_id: str | None = None
    source_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: str) -> ChatRealtimeEvent | None:
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        channel_id = payload.get("channel_id")
        event_type = payload.get("event_type")
        payload_json = payload.get("payload_json")
        if not isinstance(channel_id, str) or event_type not in {"message", "presence"}:
            return None
        if not isinstance(payload_json, str) or not _is_stream_payload_json(payload_json):
            return None
        last_message_id = payload.get("last_message_id")
        source_id = payload.get("source_id")
        return cls(
            channel_id=channel_id,
            event_type=event_type,
            payload_json=payload_json,
            last_message_id=last_message_id if isinstance(last_message_id, str) else None,
            source_id=source_id if isinstance(source_id, str) else None,
        )


class ChatRealtimeBus:
    """Fan out chat events locally and through Redis Pub/Sub when configured.

    The database remains the source of truth for history/reconnect, but hot-path events carry the
    already serialized SSE payload so connected listeners do not each reread the database.
    If Redis is unavailable, local fanout plus periodic stream polling keeps single-process
    deployments usable and reconnect-safe.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.instance_id = uuid4().hex
        self._lock = asyncio.Lock()
        self._redis_publish_lock = asyncio.Lock()
        self._redis_publish_client = None
        self._subscribers: dict[str, set[asyncio.Queue[ChatRealtimeEvent]]] = defaultdict(set)
        self._redis_tasks: dict[str, asyncio.Task[None]] = {}

    async def publish_message(self, channel_id: str, message: ChatMessageResponse) -> None:
        await self.publish(
            ChatRealtimeEvent(
                channel_id=channel_id,
                event_type="message",
                payload_json=ChatStreamResponse(messages=[message], presence=[]).model_dump_json(),
                last_message_id=message.id,
            )
        )

    async def publish_presence(self, channel_id: str, presence: ChatPresenceResponse) -> None:
        await self.publish(
            ChatRealtimeEvent(
                channel_id=channel_id,
                event_type="presence",
                payload_json=ChatStreamResponse(messages=[], presence=[presence]).model_dump_json(),
            )
        )

    async def publish(self, event: ChatRealtimeEvent) -> None:
        event = replace(event, source_id=event.source_id or self.instance_id)
        await self._fanout(event)
        if self._redis_enabled():
            asyncio.create_task(self._publish_redis(event))

    async def listen(self, channel_id: str) -> AsyncIterator[ChatRealtimeEvent]:
        queue: asyncio.Queue[ChatRealtimeEvent] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[channel_id].add(queue)
            self._ensure_redis_listener_locked(channel_id)

        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(channel_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(channel_id, None)
                        task = self._redis_tasks.pop(channel_id, None)
                        if task is not None:
                            task.cancel()

    async def _fanout(self, event: ChatRealtimeEvent) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(event.channel_id, ()))
        for queue in subscribers:
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)

    def _ensure_redis_listener_locked(self, channel_id: str) -> None:
        if not self._redis_enabled() or channel_id in self._redis_tasks:
            return
        self._redis_tasks[channel_id] = asyncio.create_task(self._redis_listener(channel_id))

    async def _publish_redis(self, event: ChatRealtimeEvent) -> None:
        try:
            client = await self._get_redis_publish_client()
            await client.publish(self._redis_channel(event.channel_id), event.to_json())
        except Exception as exc:
            logger.warning(
                "chat_realtime_redis_publish_failed",
                channel_id=event.channel_id,
                event_type=event.event_type,
                error=type(exc).__name__,
            )
            await self._reset_redis_publish_client()

    async def _get_redis_publish_client(self):
        async with self._redis_publish_lock:
            if self._redis_publish_client is None:
                self._redis_publish_client = redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=self.settings.chat_realtime_redis_timeout_seconds,
                    socket_timeout=self.settings.chat_realtime_redis_timeout_seconds,
                    health_check_interval=30,
                )
            return self._redis_publish_client

    async def _reset_redis_publish_client(self) -> None:
        async with self._redis_publish_lock:
            client = self._redis_publish_client
            self._redis_publish_client = None
        if client is not None:
            with suppress(Exception):
                await client.aclose()

    async def _redis_listener(self, channel_id: str) -> None:
        while await self._has_subscribers(channel_id):
            client = None
            pubsub = None
            try:
                client = redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=self.settings.chat_realtime_redis_timeout_seconds,
                    health_check_interval=30,
                )
                pubsub = client.pubsub()
                await pubsub.subscribe(self._redis_channel(channel_id))
                async for message in pubsub.listen():
                    if not await self._has_subscribers(channel_id):
                        return
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if not isinstance(data, str):
                        continue
                    event = ChatRealtimeEvent.from_json(data)
                    if (
                        event is not None
                        and event.channel_id == channel_id
                        and event.source_id != self.instance_id
                    ):
                        await self._fanout(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "chat_realtime_redis_listener_failed",
                    channel_id=channel_id,
                    error=type(exc).__name__,
                )
                await asyncio.sleep(self.settings.chat_realtime_redis_retry_seconds)
            finally:
                if pubsub is not None:
                    with suppress(Exception):
                        await pubsub.unsubscribe(self._redis_channel(channel_id))
                    with suppress(Exception):
                        await pubsub.aclose()
                if client is not None:
                    await client.aclose()

    async def _has_subscribers(self, channel_id: str) -> bool:
        async with self._lock:
            return bool(self._subscribers.get(channel_id))

    def _redis_enabled(self) -> bool:
        return self.settings.chat_realtime_backend in {"auto", "redis"}

    def _redis_channel(self, channel_id: str) -> str:
        return f"{self.settings.chat_realtime_redis_prefix}{channel_id}"


_chat_realtime_bus: ChatRealtimeBus | None = None


def get_chat_realtime_bus() -> ChatRealtimeBus:
    global _chat_realtime_bus

    if _chat_realtime_bus is None:
        _chat_realtime_bus = ChatRealtimeBus()
    return _chat_realtime_bus


def _is_stream_payload_json(value: str) -> bool:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return isinstance(payload.get("messages"), list) and isinstance(payload.get("presence"), list)
