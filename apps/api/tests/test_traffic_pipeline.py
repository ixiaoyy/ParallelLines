"""统计队列提交与报表的内存 SQLite/ASGI 回归，不连接 .env 数据库或真实 Redis。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.api.v1 import traffic as traffic_api
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, PermissionDeniedError
from app.db.base import Base
from app.models.traffic import TrafficDailyVisitor, TrafficEvent, TrafficVisitor
from app.schemas.traffic import TrafficQueueStatus
from app.services.traffic import _REPORT_CACHE, TrafficService
from app.services.traffic_ingest import ingest_traffic_batch
from app.services.traffic_queue import QueuedTrafficEvent
from app.workers.traffic import run_once

NOW = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
ADMIN = SimpleNamespace(role="admin")


def settings(**values) -> Settings:
    return Settings(_env_file=None, traffic_enabled=True, **values)


def queued(
    visitor="shared:visitor-a", site="games", when=NOW, name="page_view", scope="shared", **values
) -> QueuedTrafficEvent:
    return QueuedTrafficEvent(
        event_id=str(uuid4()),
        site_key=site,
        visitor_key=visitor,
        identity_scope=scope,
        event_name=name,
        path="/",
        source_type="direct",
        source_name="Direct",
        occurred_at=when,
        received_at=NOW,
        **values,
    )


class ReportRedis:
    def __init__(self):
        self.unavailable = False
        self.last_ingested = None

    async def get(self, key):
        return None

    async def set(self, *args, **kwargs):
        return True

    async def hget(self, *args):
        if self.unavailable:
            raise RedisConnectionError()
        return self.last_ingested


class ReportQueue:
    def __init__(self):
        self.client = ReportRedis()

    async def status(self):
        return TrafficQueueStatus(
            status="unavailable" if self.client.unavailable else "ok",
            pending=None if self.client.unavailable else 0,
            dropped_events=None if self.client.unavailable else 0,
        )


class SQLiteBridge:
    """复用既有测试模式：同步内存SQLite提供异步会话接口，不引入测试专用驱动依赖。"""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.session.close()

    @asynccontextmanager
    async def begin(self):
        with self.session.begin():
            yield

    async def execute(self, statement, parameters=None):
        return self.session.execute(statement, parameters)

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    def add(self, row):
        self.session.add(row)

    async def flush(self):
        self.session.flush()

    def get_bind(self):
        return self.session.get_bind()


@pytest.fixture
async def database():
    _REPORT_CACHE.clear()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[TrafficEvent.__table__, TrafficVisitor.__table__, TrafficDailyVisitor.__table__],
    )

    def factory():
        return SQLiteBridge(Session(engine, expire_on_commit=False))

    yield factory, engine
    engine.dispose()
    _REPORT_CACHE.clear()


@pytest.mark.asyncio
async def test_batch_is_idempotent_across_replay_and_uses_batched_reads(database) -> None:
    factory, engine = database
    rows = [queued(visitor=f"shared:visitor-{index}") for index in range(25)]
    queries = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda c, cu, statement, *a: queries.append(statement),
    )
    async with factory() as session:
        async with session.begin():
            assert await ingest_traffic_batch(session, rows + [rows[0]]) == 25
        assert sum(statement.lstrip().upper().startswith("SELECT") for statement in queries) == 3
        async with session.begin():
            assert await ingest_traffic_batch(session, rows) == 0
        assert await session.scalar(select(func.count()).select_from(TrafficEvent)) == 25
        assert (
            await session.scalar(
                select(func.sum(TrafficDailyVisitor.page_views)).where(
                    TrafficDailyVisitor.site_key == "all"
                )
            )
            == 25
        )


@pytest.mark.asyncio
async def test_global_uv_is_not_sum_of_site_uv_and_ephemeral_is_not_returning(database) -> None:
    factory, _ = database
    rows = [
        queued(),
        queued(site="tools"),
        queued("site:games-b", scope="site"),
        queued("site:tools-b", site="tools", scope="site"),
        queued("ephemeral:page-c", scope="ephemeral"),
        queued(name="game_open"),
    ]
    async with factory() as session:
        async with session.begin():
            await ingest_traffic_batch(session, rows)
        report = await TrafficService(session, settings(), ReportQueue(), NOW).overview(
            ADMIN, start_date=NOW.date(), end_date=NOW.date(), site_key="all"
        )
    assert report.totals.page_views == 5
    assert report.previous.page_views is None  # 未采集的上期不能当零比较。
    assert report.totals.unique_visitors == 4
    assert report.totals.shared_unique_visitors == 1
    assert report.totals.site_only_visitors == 2
    assert report.totals.ephemeral_visitors == 1
    assert report.totals.new_visitors == 3
    assert report.totals.returning_visitors == 0
    assert report.totals.actions == 1
    by_site = {site.site_key: site for site in report.sites}
    assert by_site["games"].unique_visitors == 3
    assert by_site["tools"].unique_visitors == 2
    assert by_site["chat"].status == "not_connected"
    assert by_site["chat"].page_views is None
    assert report.series[0].shared_unique_visitors == 1
    assert report.top_actions[0].event_name == "game_open"


@pytest.mark.asyncio
async def test_shanghai_day_boundary_and_new_returning_intervals(database) -> None:
    factory, _ = database
    first = datetime(2026, 11, 15, 15, 59, 59, tzinfo=UTC)  # 上海15日23:59:59
    next_day = first + timedelta(seconds=1)
    async with factory() as session:
        async with session.begin():
            await ingest_traffic_batch(session, [queued(when=first), queued(when=next_day)])
        service = TrafficService(session, settings(), ReportQueue(), NOW)
        report = await service.overview(
            ADMIN,
            start_date=date(2026, 11, 16),
            end_date=NOW.date(),
            site_key="all",
        )
        metrics = await service._metrics(
            datetime(2026, 11, 16).date(), datetime(2026, 11, 16).date(), "all"
        )
        series = await service._series(
            datetime(2026, 11, 15).date(), datetime(2026, 11, 16).date(), "all"
        )
    assert report.enabled
    assert metrics.page_views == 1
    assert metrics.new_visitors == 0
    assert metrics.returning_visitors == 1
    assert [point.page_views for point in series] == [1, 1]


@pytest.mark.asyncio
async def test_seven_day_retention_excludes_same_day_and_immature_cohorts(database) -> None:
    factory, _ = database
    start = datetime(2026, 11, 1, 8, tzinfo=UTC)
    rows = [
        queued("shared:return", when=start),
        queued("shared:return", when=start + timedelta(days=7)),
        queued("shared:same-day", when=start),
        queued("shared:same-day", when=start + timedelta(hours=1)),
        queued("shared:too-late", when=start),
        queued("shared:too-late", when=start + timedelta(days=8)),
        queued("shared:immature", when=NOW - timedelta(days=3)),
        queued("shared:immature", when=NOW - timedelta(days=1)),
        queued("ephemeral:excluded", when=start, scope="ephemeral"),
    ]
    async with factory() as session:
        async with session.begin():
            await ingest_traffic_batch(session, rows)
        report = await TrafficService(session, settings(), ReportQueue(), NOW).overview(
            ADMIN, start_date=start.date(), end_date=NOW.date(), site_key="all"
        )
    assert report.retention.eligible_visitors == 3
    assert report.retention.returned_visitors == 1
    assert report.retention.rate == 33.3
    assert report.retention.cohort_end.isoformat() == "2026-11-09"


@pytest.mark.asyncio
async def test_cached_report_refreshes_queue_health_without_rereading_sql(database) -> None:
    factory, _ = database
    queue = ReportQueue()
    async with factory() as session:
        async with session.begin():
            await ingest_traffic_batch(session, [queued()])
        service = TrafficService(session, settings(), queue, NOW)
        initial = await service.overview(
            ADMIN, start_date=NOW.date(), end_date=NOW.date(), site_key="all"
        )
    queue.client.unavailable = True

    class ForbiddenSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("cache hit must not query SQL")

    cached = await TrafficService(ForbiddenSession(), settings(), queue, NOW).overview(
        ADMIN, start_date=NOW.date(), end_date=NOW.date(), site_key="all"
    )
    assert cached.generated_at == initial.generated_at
    assert cached.totals.page_views == 1
    assert cached.queue.status == "unavailable"
    assert cached.queue.pending is None


@pytest.mark.asyncio
async def test_shared_cache_hit_does_not_restart_local_ttl(database) -> None:
    factory, _ = database
    queue = ReportQueue()
    async with factory() as session:
        service = TrafficService(session, settings(), queue, NOW)
        report = await service._build(NOW.date(), NOW.date(), "all")

        async def read_cache(key):
            return report.model_dump_json()

        queue.client.get = read_cache
        assert await service._read_shared_cache("cache-hit") is not None
        assert _REPORT_CACHE.get("cache-hit") is None


@pytest.mark.asyncio
async def test_permissions_disabled_state_and_unconnected_state_are_distinct(database) -> None:
    factory, _ = database
    async with factory() as session:
        service = TrafficService(session, settings(), ReportQueue(), NOW)
        with pytest.raises(PermissionDeniedError):
            await service.overview(
                SimpleNamespace(role="user"), start_date=None, end_date=None, site_key="all"
            )
        unconnected = await service.overview(
            ADMIN, start_date=NOW.date(), end_date=NOW.date(), site_key="all"
        )
        assert unconnected.status == "not_connected"
        assert unconnected.totals.page_views is None
        disabled = await TrafficService(session, Settings(_env_file=None), now=NOW).overview(
            ADMIN, start_date=None, end_date=None, site_key="all"
        )
        assert disabled.status == "disabled"
        assert disabled.totals.unique_visitors is None


class WorkerRedis:
    def __init__(self):
        self.lock = None
        self.meta = {}

    async def set(self, key, value, **kwargs):
        if self.lock is not None:
            return False
        self.lock = value
        return True

    async def hset(self, key, field, value):
        self.meta[field] = value

    async def eval(self, script, count, key, owner):
        if self.lock == owner:
            self.lock = None
        return 1


class WorkerQueue:
    def __init__(self, rows, fail_ack=False):
        self.client = WorkerRedis()
        self.messages = [(f"{index}-0", row) for index, row in enumerate(rows)]
        self.fail_ack = fail_ack
        self.acknowledged = False

    async def claim(self, consumer):
        return self.messages

    async def acknowledge(self, ids):
        if self.fail_ack:
            self.fail_ack = False
            raise OSError("simulated disconnect after SQL commit")
        self.acknowledged = True
        self.messages = []


@pytest.mark.asyncio
async def test_worker_recovers_after_commit_before_ack_without_double_count(database) -> None:
    factory, _ = database
    queue = WorkerQueue([queued()], fail_ack=True)
    with pytest.raises(OSError):
        await run_once(settings=settings(), session_factory=factory, queue=queue)
    assert not queue.acknowledged
    assert queue.client.meta["last_ingested_at"]
    assert await run_once(settings=settings(), session_factory=factory, queue=queue) == 0
    assert queue.acknowledged
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(TrafficEvent)) == 1
        assert (
            await session.scalar(
                select(func.sum(TrafficDailyVisitor.page_views)).where(
                    TrafficDailyVisitor.site_key == "all"
                )
            )
            == 1
        )


@pytest.mark.asyncio
async def test_worker_rolls_back_failed_batch_and_leaves_messages_for_retry(
    database, monkeypatch
) -> None:
    factory, _ = database
    queue = WorkerQueue([queued()])

    async def fail_after_flush(session, rows):
        await ingest_traffic_batch(session, rows)
        raise RuntimeError("simulated failure before commit")

    monkeypatch.setattr("app.workers.traffic.ingest_traffic_batch", fail_after_flush)
    with pytest.raises(RuntimeError):
        await run_once(settings=settings(), session_factory=factory, queue=queue)
    assert not queue.acknowledged
    assert "last_ingested_at" not in queue.client.meta
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(TrafficEvent)) == 0
        assert await session.scalar(select(func.count()).select_from(TrafficDailyVisitor)) == 0
    monkeypatch.setattr("app.workers.traffic.ingest_traffic_batch", ingest_traffic_batch)
    assert await run_once(settings=settings(), session_factory=factory, queue=queue) == 1
    assert queue.acknowledged


@pytest.mark.asyncio
async def test_public_asgi_collect_has_no_database_dependency_and_supports_plain_cors(
    monkeypatch,
) -> None:
    app = FastAPI()
    app.include_router(traffic_api.router, prefix="/api/v1")
    app.dependency_overrides[get_settings] = lambda: settings()

    @app.exception_handler(AppError)
    async def handle(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code})

    captured = []

    class CollectQueue:
        def __init__(self, _settings):
            pass

        async def enqueue(self, rows):
            captured.extend(rows)
            return len(rows)

    monkeypatch.setattr(traffic_api, "TrafficQueue", CollectQueue)
    payload = {
        "visitor_id": "browser-test-1234",
        "identity_scope": "shared",
        "events": [
            {
                "event_id": str(uuid4()),
                "site_key": "tools",
                "event_name": "page_view",
                "path": "/?file=private",
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    import json

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/site/traffic",
            content=json.dumps(payload),
            headers={
                "Origin": "https://tools.pingxingxian.space",
                "Content-Type": "text/plain",
                "User-Agent": "Mozilla/5.0",
            },
        )
        assert response.status_code == 202
        assert response.json()["data"]["accepted"] == 1
        assert response.headers["access-control-allow-origin"] == "https://tools.pingxingxian.space"
        assert captured[0].path == "/"
        denied = await client.post(
            "/api/v1/site/traffic", json=payload, headers={"Origin": "https://evil.example"}
        )
        assert denied.status_code == 403
        too_large = await client.post("/api/v1/site/traffic", content="x" * 17000)
        assert too_large.status_code == 413
