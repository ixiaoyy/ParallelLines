"""跨站统计的隔离回归；不加载 .env，不连接项目数据库或真实 Redis。"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError, PermissionDeniedError, ValidationError
from app.schemas.traffic import TrafficBatchRequest
from app.services.traffic_queue import (
    TrafficQueue,
    normalize_traffic_batch,
    normalize_traffic_path,
    validate_traffic_origin,
)

NOW = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)


def batch(
    site_key: str = "games", scope: str = "shared", **event_values: object
) -> TrafficBatchRequest:
    event = {
        "event_id": str(uuid4()),
        "site_key": site_key,
        "event_name": "page_view",
        "path": "/games?search=private#secret",
        "occurred_at": NOW.isoformat(),
        "referrer": "https://www.google.com/search?q=private",
        **event_values,
    }
    return TrafficBatchRequest.model_validate(
        {"visitor_id": "browser-local-1234", "identity_scope": scope, "events": [event]}
    )


def normalized(site_key: str = "games", scope: str = "shared", **values: object):
    origin = (
        "https://pingxingxian.space"
        if site_key == "games"
        else f"https://{site_key}.pingxingxian.space"
    )
    return normalize_traffic_batch(
        batch(site_key, scope, **values),
        origin=origin,
        user_agent="Mozilla/5.0",
        settings=settings(),
        now=NOW,
    )[1]


def test_shared_identity_deduplicates_across_sites_but_fallback_identity_does_not() -> None:
    assert normalized()[0].visitor_key == normalized("tools")[0].visitor_key
    assert normalized(scope="site")[0].visitor_key != normalized("tools", "site")[0].visitor_key
    assert (
        normalized(scope="ephemeral")[0].visitor_key
        != normalized("tools", "ephemeral")[0].visitor_key
    )
    assert "browser-local-1234" not in normalized()[0].model_dump_json()


@pytest.mark.parametrize("site", ["games", "forum", "tools"])
def test_main_origin_allows_retained_legacy_routes(site: str) -> None:
    validate_traffic_origin("https://pingxingxian.space", {site}, settings())


@pytest.mark.parametrize(
    "origin,sites",
    [
        ("https://evil.example", {"games"}),
        ("https://tools.pingxingxian.space", {"chat"}),
        ("http://pingxingxian.space", {"games"}),
        (None, {"games"}),
        ("https://tools.pingxingxian.space/path", {"tools"}),
        ("https://tools.pingxingxian.space?secret=token", {"tools"}),
    ],
)
def test_origin_must_match_explicit_site_mapping(origin, sites) -> None:
    with pytest.raises(PermissionDeniedError):
        validate_traffic_origin(origin, sites, settings())


def test_loopback_requires_explicit_flag() -> None:
    with pytest.raises(PermissionDeniedError):
        validate_traffic_origin("http://localhost:5173", {"games"}, settings())
    validate_traffic_origin(
        "http://localhost:5173", {"games"}, settings(traffic_allow_loopback=True)
    )


def test_privacy_and_source_are_normalized_before_queueing() -> None:
    event = normalized()[0]
    assert event.path == "/games"
    assert normalized(path="/games%3Fsecret=hidden%23fragment")[0].path == "/games"
    assert event.source_type == "search"
    assert event.source_name == "www.google.com"
    assert "private" not in event.model_dump_json()
    assert normalized("chat", path="/c/private-chat-id?token=secret")[0].path == "/c/:chat"
    assert normalized("forum", path="/members/private-user")[0].path == "/members/:member"
    assert normalized(campaign_source="release_2026")[0].source_type == "campaign"
    assert (
        normalized(referrer="https://tools.pingxingxian.space/private")[0].source_type == "internal"
    )


@pytest.mark.parametrize(
    "path",
    ["/admin/analytics", "/auth/callback?code=secret", "//evil.example", "https://evil.example/"],
)
def test_management_and_external_paths_do_not_enter_traffic(path: str) -> None:
    assert normalize_traffic_path(path, "games") is None


@pytest.mark.parametrize("delta", [timedelta(days=-2), timedelta(minutes=6)])
def test_time_window_is_bounded(delta: timedelta) -> None:
    with pytest.raises(ValidationError):
        normalized(occurred_at=(NOW + delta).isoformat())


def test_bots_are_not_enqueued() -> None:
    _, events = normalize_traffic_batch(
        batch(),
        origin="https://pingxingxian.space",
        user_agent="Googlebot/1.0",
        settings=settings(),
        now=NOW,
    )
    assert events == []


class FakeRedis:
    def __init__(self, result=1):
        self.result = result
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return self.result


@pytest.mark.asyncio
async def test_enqueue_is_one_bounded_redis_operation_and_never_uses_sql() -> None:
    client = FakeRedis()
    assert await TrafficQueue(settings(), client).enqueue(normalized()) == 1
    assert len(client.calls) == 1
    assert client.calls[0][1] == 3
    assert client.calls[0][5] == 20000


@pytest.mark.asyncio
@pytest.mark.parametrize("result,code", [(-1, "traffic_queue_full"), (-2, "traffic_rate_limited")])
async def test_capacity_and_rate_failures_are_not_reported_as_success(result, code) -> None:
    with pytest.raises(AppError) as caught:
        await TrafficQueue(settings(), FakeRedis(result)).enqueue(normalized())
    assert caught.value.code == code
    assert caught.value.status_code == 429


@pytest.mark.asyncio
async def test_redis_request_has_total_deadline_and_no_retry_loop() -> None:
    class SlowRedis:
        async def eval(self, *args):
            await asyncio.sleep(10)

    queue = TrafficQueue(settings(traffic_redis_timeout_seconds=0.05), SlowRedis())
    with pytest.raises(AppError) as caught:
        await asyncio.wait_for(queue.enqueue(normalized()), timeout=0.5)
    assert caught.value.code == "traffic_queue_unavailable"
