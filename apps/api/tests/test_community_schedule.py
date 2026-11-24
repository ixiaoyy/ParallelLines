from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.community_content import CommunityContentSettings
from app.db.base import SHANGHAI_TZ
from app.services.community_schedule import (
    CONTENT_CHANNELS,
    CONTENT_QUEUE,
    CONTENT_TASK,
    content_payload,
    content_slot_is_current,
    due_content_slots,
    enqueue_content_slots,
    parse_content_payload,
)


def local(hour: int, minute: int = 0, *, day: int = 15) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=SHANGHAI_TZ)


def test_three_daily_times_include_weekends_and_never_rotate_channels() -> None:
    # 2026-11-15 为周日；海外合集加到末尾，原五项及生活小问停用规则保持不变。
    start = local(9)
    for hour in (10, 14, 18):
        assert due_content_slots(local(hour), start) == [local(hour)]
    assert CONTENT_CHANNELS == (
        "weibo_snapshot", "news", "sports", "hot_search", "reading", "overseas"
    )
    assert len(set(CONTENT_CHANNELS)) == 6


def test_lightweight_heartbeat_requires_recent_valid_poll(tmp_path, monkeypatch) -> None:
    from datetime import timedelta

    from app.workers import community_content_health as health

    path = tmp_path / "heartbeat"
    monkeypatch.setattr(health, "HEARTBEAT", path)
    assert not health.worker_is_healthy()
    path.write_text(datetime.now(UTC).isoformat(), encoding="ascii")
    assert health.worker_is_healthy()
    path.write_text((datetime.now(UTC) - timedelta(minutes=6)).isoformat(), encoding="ascii")
    assert not health.worker_is_healthy()
    path.write_text("invalid", encoding="ascii")
    assert not health.worker_is_healthy()


def test_activation_watermark_and_bounded_current_slot() -> None:
    assert due_content_slots(local(10, 1), local(10, 1)) == []
    assert due_content_slots(local(9, 59), local(8)) == []
    assert due_content_slots(local(10, 29), local(8)) == [local(10)]
    assert due_content_slots(local(10, 30), local(8)) == []
    assert due_content_slots(local(14), local(10, 1)) == [local(14)]
    assert due_content_slots(local(8, day=16), local(8)) == []
    assert due_content_slots(local(18), local(19)) == []


def test_utc_input_is_scheduled_in_shanghai() -> None:
    assert due_content_slots(datetime(2026, 11, 15, 2, tzinfo=UTC), local(9)) == [local(10)]
    with pytest.raises(ValueError):
        due_content_slots(datetime(2026, 11, 15, 10), local(9))


def test_payload_roundtrip_rejects_inconsistent_dates_or_unknown_channel() -> None:
    payload = content_payload("reading", local(14))
    assert parse_content_payload(payload) == ("reading", local(14))
    for changed in (
        {"channel": "seed_persona_engagement"},
        {"channel": "living"},
        {"planned_date": "2026-11-14"},
        {"scheduled_time": "10:00"},
        {"scheduled_for": "2026-11-15T14:00:00"},
    ):
        with pytest.raises(ValueError):
            parse_content_payload({**payload, **changed})


def test_expired_retry_never_publishes_or_crosses_activation_watermark() -> None:
    assert content_slot_is_current(local(10), local(10, 3), local(9))
    assert not content_slot_is_current(local(10), local(10, 30), local(9))
    assert not content_slot_is_current(local(10), local(10, 3), local(10, 1))


@pytest.mark.asyncio
async def test_enqueue_adds_overseas_without_changing_existing_job_keys() -> None:
    service = SimpleNamespace(enqueue=AsyncMock(), session=SimpleNamespace(commit=AsyncMock()))
    assert await enqueue_content_slots(service, now=local(10), start_at=local(9)) == 6
    first = list(service.enqueue.await_args_list)
    assert {call.kwargs["payload"]["channel"] for call in first} == {
        "weibo_snapshot", "news", "sports", "hot_search", "reading", "overseas"
    }
    assert all(call.args == (CONTENT_TASK,) for call in first)
    assert all(call.kwargs["queue"] == CONTENT_QUEUE for call in first)
    assert [call.kwargs["idempotency_key"] for call in first] == [
        f"community:v1:2026-11-15:10:{channel}" for channel in CONTENT_CHANNELS
    ]
    assert len({call.kwargs["idempotency_key"] for call in first}) == 6
    assert await enqueue_content_slots(service, now=local(10, 1), start_at=local(9)) == 6
    assert [call.kwargs["idempotency_key"] for call in first] == [
        call.kwargs["idempotency_key"] for call in service.enqueue.await_args_list[6:]
    ]


def test_new_settings_default_off_and_require_explicit_aware_watermark() -> None:
    assert not CommunityContentSettings(_env_file=None).enabled
    with pytest.raises(ValidationError):
        CommunityContentSettings(enabled=True, _env_file=None)
    with pytest.raises(ValidationError):
        CommunityContentSettings(enabled=True, start_at="2026-11-15T10:00:00", _env_file=None)
    assert CommunityContentSettings(enabled=True, start_at=local(9), _env_file=None).enabled


def test_persona_return_must_be_a_real_publication_not_preview_or_silent_failure() -> None:
    from app.core.exceptions import AppError
    from app.workers.community_content import require_persona_publication

    success = {
        "dry_run": False,
        "publish_mode": "auto",
        "results": [{"status": "created", "topic_id": "1"}],
    }
    assert require_persona_publication(success, "reading") is success
    for change in (
        {"dry_run": True},
        {"publish_mode": "off"},
        {"results": []},
        {"results": [{"status": "failed", "topic_id": None}]},
    ):
        with pytest.raises(AppError):
            require_persona_publication({**success, **change}, "reading")


@pytest.mark.asyncio
async def test_retired_living_job_completes_as_skipped_without_parsing_or_publication(
    monkeypatch,
) -> None:
    from app.workers import community_content as worker

    def must_not_run(*args, **kwargs):
        raise AssertionError("Retired living job must not enter scheduling or publication")

    monkeypatch.setattr(worker, "CommunityContentSettings", must_not_run)
    monkeypatch.setattr(worker, "parse_content_payload", must_not_run)
    monkeypatch.setattr(worker, "get_settings", must_not_run)
    payload = {**content_payload("reading", local(10)), "channel": "living"}
    job = SimpleNamespace(id="retired-living", task_name=CONTENT_TASK, payload=payload, attempts=1)
    session = SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock())
    service = worker.ContentQueueService(session)
    monkeypatch.setattr(service, "acquire_next", AsyncMock(return_value=job))
    monkeypatch.setattr(service, "_add_log", lambda *args, **kwargs: None)

    result = await service.run_next(
        {CONTENT_TASK: worker.handle_content_slot}, worker_id="test", queues=(CONTENT_QUEUE,)
    )

    assert result.status == "succeeded"
    assert result.result == {"status": "skipped", "reason": "living_retired", "channel": "living"}
    assert result.last_error is None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "channel", ("weibo_snapshot", "news", "sports", "hot_search", "reading", "overseas")
)
async def test_remaining_channels_keep_existing_publication_calls(channel, monkeypatch) -> None:
    from app.services import daily_reading, scheduled_content
    from app.workers import community_content as worker

    settings = object()
    session = object()
    scheduled = local(10)
    publication = {
        "dry_run": False,
        "publish_mode": "auto",
        "results": [{"status": "created", "topic_id": "reading-1"}],
    }
    reading = SimpleNamespace(publish_day=AsyncMock(return_value=publication))
    scheduled_service = SimpleNamespace(
        collect_hot_search=AsyncMock(return_value={"status": "collected"}),
        publish_slot=AsyncMock(return_value={"status": "published"}),
    )
    monkeypatch.setattr(
        worker, "CommunityContentSettings", lambda: SimpleNamespace(enabled=True, start_at=local(9))
    )
    monkeypatch.setattr(worker, "utcnow", lambda: scheduled)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)

    def reading_factory(received_session, received_settings):
        assert received_session is session
        assert received_settings is settings
        return reading

    def scheduled_factory(received_session, received_settings):
        assert received_session is session
        assert received_settings is settings
        return scheduled_service

    monkeypatch.setattr(daily_reading, "DailyReadingService", reading_factory)
    monkeypatch.setattr(scheduled_content, "ScheduledContentService", scheduled_factory)

    result = await worker.handle_content_slot(session, content_payload(channel, scheduled))

    if channel == "reading":
        assert result is publication
        reading.publish_day.assert_awaited_once_with(
            scheduled.date(), scheduled_time="10:00", dry_run=False
        )
        scheduled_service.collect_hot_search.assert_not_awaited()
        scheduled_service.publish_slot.assert_not_awaited()
    elif channel == "weibo_snapshot":
        assert result == {"status": "collected"}
        scheduled_service.collect_hot_search.assert_awaited_once_with(scheduled, persist=True)
        scheduled_service.publish_slot.assert_not_awaited()
        reading.publish_day.assert_not_awaited()
    else:
        assert result == {"status": "published"}
        scheduled_service.publish_slot.assert_awaited_once_with(channel, scheduled, dry_run=False)
        scheduled_service.collect_hot_search.assert_not_awaited()
        reading.publish_day.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_transient_content_failures_use_existing_bounded_retry(monkeypatch) -> None:
    from app.services.background_jobs import BackgroundJobService
    from app.workers.community_content import ContentQueueService

    session = SimpleNamespace(rollback=AsyncMock())
    service = ContentQueueService(session)
    dead = AsyncMock(return_value="dead")
    retry = AsyncMock(return_value="retry")
    monkeypatch.setattr(service, "_mark_dead", dead)
    monkeypatch.setattr(BackgroundJobService, "_mark_retry_or_dead", retry)
    assert (
        await service._mark_retry_or_dead(
            "1", error="permanent_content:identity", retry_delay_seconds=60
        )
        == "dead"
    )
    dead.assert_awaited_once()
    retry.assert_not_awaited()
    assert (
        await service._mark_retry_or_dead(
            "2", error="retryable_content:TimeoutError", retry_delay_seconds=60
        )
        == "retry"
    )
    retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_content_job_is_explicitly_refreshed_after_service_transaction(monkeypatch) -> None:
    from app.workers.community_content import ContentQueueService

    session = SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock())
    service = ContentQueueService(session)
    job = SimpleNamespace(id="1", task_name=CONTENT_TASK, payload={}, attempts=1)
    monkeypatch.setattr(service, "acquire_next", AsyncMock(return_value=job))
    monkeypatch.setattr(service, "_add_log", lambda *args, **kwargs: None)
    handler = AsyncMock(return_value={"status": "no_candidate"})
    result = await service.run_next({CONTENT_TASK: handler}, worker_id="test")
    assert result.status == "succeeded"
    assert session.refresh.await_count == 2
    assert result.result == {"status": "no_candidate"}
