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
    # 2026-11-15 为周日；每个时段都应包含全部六项。
    start = local(9)
    for hour in (10, 14, 18):
        assert due_content_slots(local(hour), start) == [local(hour)]
    assert len(CONTENT_CHANNELS) == 6
    assert len(set(CONTENT_CHANNELS)) == 6


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
async def test_enqueue_creates_six_separate_jobs_with_stable_keys() -> None:
    service = SimpleNamespace(enqueue=AsyncMock(), session=SimpleNamespace(commit=AsyncMock()))
    assert await enqueue_content_slots(service, now=local(10), start_at=local(9)) == 6
    first = list(service.enqueue.await_args_list)
    assert {call.kwargs["payload"]["channel"] for call in first} == set(CONTENT_CHANNELS)
    assert all(call.args == (CONTENT_TASK,) for call in first)
    assert all(call.kwargs["queue"] == CONTENT_QUEUE for call in first)
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
