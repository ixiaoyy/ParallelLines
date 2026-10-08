import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.background_jobs import BackgroundJobService, daily_reading_due_slots
from app.services.daily_reading import (
    DAILY_READING_AVATAR_URL,
    DAILY_READING_BIO,
    DAILY_READING_EMAIL,
    DAILY_READING_USERNAME,
    DailyReadingPlan,
    DailyReadingPublishResult,
    DailyReadingService,
    daily_reading_seed_key,
)
from app.services.daily_reading_provider import (
    DAILY_READING_TAGS,
    build_local_daily_reading_drafts,
    parse_daily_reading_provider_result,
)
from app.workers import background_jobs


class _PersonaSessionDouble:
    """Provide the minimal async session surface for persona refresh tests."""

    def __init__(self, user: object | None) -> None:
        """Store one scalar result and initialize mutation counters."""

        self.user = user
        self.added: list[object] = []
        self.flush_count = 0

    async def scalar(self, _statement: object) -> object | None:
        """Return the configured user for any scalar query without side effects."""

        return self.user

    def add(self, value: object) -> None:
        """Record an added model so tests can inspect write intent."""

        self.added.append(value)

    async def flush(self) -> None:
        """Record that the service flushed its account update."""

        self.flush_count += 1


class _CommitSessionDouble:
    """Provide only the commit surface needed by scheduled-job planning."""

    def __init__(self) -> None:
        """Initialize the commit counter without performing I/O."""

        self.commit_count = 0

    async def commit(self) -> None:
        """Record the scheduler's single batched commit."""

        self.commit_count += 1


def test_local_fallback_builds_two_distinct_date_stable_drafts() -> None:
    """Each date must always produce two different books and titles."""

    planned_date = date(2026, 8, 12)
    first = build_local_daily_reading_drafts(planned_date)
    repeated = build_local_daily_reading_drafts(planned_date)

    assert first == repeated
    assert len(first) == 2
    assert first[0].title != first[1].title
    assert first[0].raw_md != first[1].raw_md
    assert first[0].title.split("：", 1)[-1] != first[1].title.split("：", 1)[-1]
    assert all(draft.tags == DAILY_READING_TAGS for draft in first)
    assert all(120 <= len(draft.raw_md) <= 1600 for draft in first)


def test_local_fallback_does_not_repeat_titles_for_960_days() -> None:
    """The curated fallback must sustain two fresh title combinations per day."""

    start = date(2026, 1, 1)
    titles = [
        draft.title
        for offset in range(960)
        for draft in build_local_daily_reading_drafts(start + timedelta(days=offset))
    ]

    assert len(titles) == 1920
    assert len(set(titles)) == len(titles)


def test_provider_parser_accepts_exactly_two_valid_posts() -> None:
    """Valid model JSON should become two normalized daily-reading drafts."""

    body_one = "第一段先记下今天读到的感受。\n\n" + "这不是摘抄，而是自己的理解。" * 16
    body_two = "另一本书带来了不同的问题。\n\n" + "我想把答案留到明天再看。" * 16
    response = {
        "model": "unit-model",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "posts": [
                                {"title": "  今天只记一个问题  ", "body": body_one},
                                {"title": "隔夜以后再想一遍", "body": body_two},
                            ]
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ],
    }

    result = parse_daily_reading_provider_result(response, fallback_model="fallback")

    assert result.model_name == "unit-model"
    assert result.provider_mode == "ai"
    assert [draft.title for draft in result.drafts] == [
        "今天只记一个问题",
        "隔夜以后再想一遍",
    ]


def test_provider_parser_rejects_any_count_other_than_two() -> None:
    """One or three posts must fail closed instead of changing daily volume."""

    response = {
        "choices": [
            {
                "message": {
                    "content": '{"posts":[{"title":"只有一篇不行","body":"'
                    + "正文" * 70
                    + '"}]}'
                }
            }
        ]
    }

    with pytest.raises(AppError) as exc_info:
        parse_daily_reading_provider_result(response, fallback_model="fallback")

    assert exc_info.value.code == "daily_reading_provider_invalid_response"


def test_daily_reading_seed_key_is_date_and_slot_stable() -> None:
    """The two daily audit identities must be stable and reject unknown slots."""

    planned_date = date(2026, 8, 12)

    assert daily_reading_seed_key(planned_date, 1) == "daily-reading:2026-08-12:01"
    assert daily_reading_seed_key(planned_date, 2) == "daily-reading:2026-08-12:02"
    with pytest.raises(ValueError):
        daily_reading_seed_key(planned_date, 3)


def test_daily_reading_publish_times_are_configurable_and_ordered() -> None:
    """Runtime settings must accept two distinct ascending Shanghai times."""

    settings = Settings(
        _env_file=None,
        daily_reading_publish_times=["07:55", "08:25"],
    )

    assert settings.daily_reading_publish_times == ("07:55", "08:25")
    with pytest.raises(ValueError):
        Settings(_env_file=None, daily_reading_publish_times=["08:30", "08:00"])


@pytest.mark.asyncio
async def test_scheduler_no_longer_enqueues_due_daily_reading_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """改版后即使阅读档期已到，也不会自动创建论坛发布任务。"""

    scheduled_at = datetime(2026, 8, 12, 0, 15, tzinfo=UTC)
    session = _CommitSessionDouble()
    service = BackgroundJobService(cast(AsyncSession, session))
    enqueue = AsyncMock(return_value=SimpleNamespace(id="reading-slot-1"))
    monkeypatch.setattr(service, "enqueue", enqueue)

    jobs = await service.enqueue_due_scheduled_jobs(
        background_upload_cleanup_interval_seconds=0,
        background_session_cleanup_interval_seconds=0,
        now=scheduled_at,
    )

    assert jobs == []
    assert session.commit_count == 1
    enqueue.assert_not_awaited()


def test_daily_reading_slots_become_due_separately() -> None:
    """Slot two must remain pending until 08:30 Shanghai while slot one is already due."""

    just_after_first = datetime(2026, 8, 12, 0, 5, tzinfo=UTC)
    just_after_second = datetime(2026, 8, 12, 0, 35, tzinfo=UTC)

    first_due = daily_reading_due_slots(just_after_first, ("08:00", "08:30"))
    second_due = daily_reading_due_slots(just_after_second, ("08:00", "08:30"))

    assert [slot for slot, _, _ in first_due] == [1]
    assert [slot for slot, _, _ in second_due] == [1, 2]


@pytest.mark.asyncio
async def test_existing_persona_is_refreshed_and_kept_out_of_growth_metrics() -> None:
    """Runtime account refresh must always persist profile and persona fields."""

    user = SimpleNamespace(
        username=DAILY_READING_USERNAME,
        email=DAILY_READING_EMAIL,
        display_name="old",
        bio="old",
        avatar_url=None,
        role="user",
        status="active",
        is_persona=False,
    )
    session = _PersonaSessionDouble(user)
    service = DailyReadingService(cast(AsyncSession, session), Settings(_env_file=None))

    assert await service._ensure_persona() is user
    assert user.display_name == DAILY_READING_USERNAME
    assert user.bio == DAILY_READING_BIO
    assert user.avatar_url == DAILY_READING_AVATAR_URL
    assert user.role == "user"
    assert user.status == "active"
    assert user.is_persona is True
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_off_mode_skips_generation_without_a_database_session() -> None:
    """Disabled publishing must not read storage or call the content provider."""

    service = DailyReadingService(None, Settings(_env_file=None))

    result = await service.publish_day(
        date(2026, 8, 12),
        publish_mode="off",
    )

    assert result == {
        "dry_run": True,
        "publish_mode": "off",
        "planned_date": "2026-08-12",
        "status": "skipped",
        "reason": "daily_reading_off",
        "plans": [],
        "results": [],
    }


@pytest.mark.asyncio
async def test_partial_day_retry_only_publishes_the_missing_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry after slot one succeeds must only execute slot two's write path."""

    planned_date = date(2026, 8, 12)
    plans = [
        DailyReadingPlan(
            seed_key=daily_reading_seed_key(planned_date, slot),
            planned_date=planned_date,
            slot=slot,
            title=f"第 {slot} 篇",
            raw_md="正文" * 100,
            tags=DAILY_READING_TAGS,
            model_name="local",
            provider_mode="local_fallback",
        )
        for slot in (1, 2)
    ]
    existing = DailyReadingPublishResult(
        seed_key=plans[0].seed_key,
        slot=1,
        title=plans[0].title,
        status="existing",
        topic_id="topic-1",
    )
    service = DailyReadingService(cast(AsyncSession, object()), Settings(_env_file=None))
    monkeypatch.setattr(service, "_existing_day_results", AsyncMock(return_value=[existing]))
    monkeypatch.setattr(service, "_stored_or_new_plans", AsyncMock(return_value=plans))
    publish_plan = AsyncMock(
        return_value=DailyReadingPublishResult(
            seed_key=plans[1].seed_key,
            slot=2,
            title=plans[1].title,
            status="created",
            topic_id="topic-2",
        )
    )
    monkeypatch.setattr(service, "_publish_plan", publish_plan)

    result = await service.publish_day(planned_date, publish_mode="auto")

    publish_plan.assert_awaited_once_with(plans[1])
    assert [item["status"] for item in result["results"]] == ["existing", "created"]


@pytest.mark.asyncio
async def test_scheduled_slot_publishes_only_that_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An 08:00 run must not publish slot two before its own scheduled time."""

    planned_date = date(2026, 8, 12)
    plans = [
        DailyReadingPlan(
            seed_key=daily_reading_seed_key(planned_date, slot),
            planned_date=planned_date,
            slot=slot,
            title=f"第 {slot} 篇",
            raw_md="正文" * 100,
            tags=DAILY_READING_TAGS,
            model_name="local",
            provider_mode="local_fallback",
        )
        for slot in (1, 2)
    ]
    service = DailyReadingService(cast(AsyncSession, object()), Settings(_env_file=None))
    monkeypatch.setattr(service, "_existing_day_results", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_stored_or_new_plans", AsyncMock(return_value=plans))
    publish_plan = AsyncMock(
        return_value=DailyReadingPublishResult(
            seed_key=plans[0].seed_key,
            slot=1,
            title=plans[0].title,
            status="created",
            topic_id="topic-1",
        )
    )
    monkeypatch.setattr(service, "_publish_plan", publish_plan)

    result = await service.publish_day(planned_date, publish_mode="auto", slots=(1,))

    publish_plan.assert_awaited_once_with(plans[0])
    assert [item["slot"] for item in result["results"]] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("publish_mode", "expected_dry_run"),
    [("auto", False), ("preview", True), ("off", True)],
)
async def test_worker_delegates_to_daily_reading_service_mode(
    monkeypatch: pytest.MonkeyPatch,
    publish_mode: str,
    expected_dry_run: bool,
) -> None:
    """The scheduled handler must only permit writes in explicit auto mode."""

    calls: list[tuple[object, date, tuple[int, ...], bool]] = []

    class _ReadingService:
        """Capture worker orchestration without opening a database session."""

        def __init__(self, session: AsyncSession, _settings: Settings) -> None:
            """Store the worker session for the later publish assertion."""

            self.session = session

        async def publish_day(
            self,
            planned_date: date,
            *,
            dry_run: bool,
            slots: tuple[int, ...],
        ) -> dict[str, object]:
            """Return a tiny summary after recording the requested mode."""

            calls.append((self.session, planned_date, slots, dry_run))
            return {"dry_run": dry_run, "slots": list(slots), "results": []}

    settings = Settings(_env_file=None, daily_reading_publish_mode=publish_mode)
    monkeypatch.setattr(background_jobs, "get_settings", lambda: settings)
    monkeypatch.setattr(background_jobs, "DailyReadingService", _ReadingService)
    session = cast(AsyncSession, object())

    result = await background_jobs.handle_publish_daily_reading(
        session,
        {"planned_date": "2026-08-12", "slot": 2},
    )

    assert calls == [(session, date(2026, 8, 12), (2,), expected_dry_run)]
    assert result == {"dry_run": expected_dry_run, "slots": [2], "results": []}
