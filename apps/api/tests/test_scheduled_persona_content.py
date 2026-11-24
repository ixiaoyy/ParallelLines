"""三时段生活/读书纯逻辑回归；所有存储与模型边界均使用替身。"""

import json
from datetime import date, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services import daily_reading as reading_module
from app.services import living_forum as living_module
from app.services.daily_reading import (
    DAILY_READING_AUTOMATION_MARKER,
    DAILY_READING_EMAIL,
    DAILY_READING_USERNAME,
    DailyReadingPublishResult,
    DailyReadingService,
    daily_reading_plan_key,
    daily_reading_seed_key,
)
from app.services.daily_reading_provider import (
    DAILY_READING_SCHEDULED_TIMES,
    DAILY_READING_SYSTEM_PROMPT,
    build_daily_reading_messages,
    build_local_scheduled_reading_draft,
    parse_daily_reading_provider_result,
)
from app.services.living_forum import (
    PERSONAS,
    LivingForumService,
)
from scripts.plan_living_forum_day import parse_args as parse_living_args
from scripts.publish_daily_reading import parse_args as parse_reading_args


def settings() -> Settings:
    """返回不读真实.env且不调用模型的测试配置。"""

    return Settings(_env_file=None, daily_reading_ai_provider="local")


def test_living_three_slots_have_distinct_content_and_no_poll() -> None:
    """每个真实时段仅一篇不同话题，不以改日期/改键重复同稿。"""

    planned_date = date(2026, 11, 15)
    service = LivingForumService(None, settings())
    plans = [
        service.plan_day(planned_date, scheduled_time=time)[0]
        for time in DAILY_READING_SCHEDULED_TIMES
    ]

    assert len({plan.seed_key for plan in plans}) == 3
    assert len({plan.title for plan in plans}) == 3
    assert len({plan.raw_md for plan in plans}) == 3
    assert all(plan.planned_date == planned_date for plan in plans)
    assert all(plan.poll is None and plan.board_slug == "lounge" for plan in plans)
    assert all(f"专用账号{plan.author}自动生成" in plan.raw_md for plan in plans)
    assert plans == [
        service.plan_day(planned_date, scheduled_time=time)[0]
        for time in DAILY_READING_SCHEDULED_TIMES
    ]
    assert service.plan_day(planned_date) == service.plan_day(planned_date, scheduled_time=None)
    assert len(service.plan_day(planned_date)) == 5
    with pytest.raises(ValueError):
        service.plan_day(planned_date, scheduled_time="09:00")


def test_living_authors_follow_their_topic_mapping() -> None:
    """轮换内容保留原有专用人设，不把生活栏目统一替换为一个账号。"""

    service = LivingForumService(None, settings())
    plans = [
        service.plan_day(date(2026, 11, 15) + timedelta(days=day), scheduled_time=time)[0]
        for day in range(8)
        for time in DAILY_READING_SCHEDULED_TIMES
    ]
    assert {plan.author for plan in plans} == {"老槐", "rain_404", "远山便利店", "雾里看山"}
    assert all(plan.author in PERSONAS for plan in plans)


@pytest.mark.asyncio
async def test_reading_three_slots_are_single_distinct_marked_drafts() -> None:
    """本地三时段不改真实日期，每批一篇，旧日更仍返回两篇。"""

    planned_date = date(2026, 11, 15)
    service = DailyReadingService(None, settings())
    batches = [
        await service.plan_day(planned_date, force_local=True, scheduled_time=time)
        for time in DAILY_READING_SCHEDULED_TIMES
    ]
    assert [len(batch) for batch in batches] == [1, 1, 1]
    plans = [batch[0] for batch in batches]
    assert len({plan.title for plan in plans}) == 3
    assert len({plan.raw_md for plan in plans}) == 3
    assert len({plan.seed_key for plan in plans}) == 3
    assert all(plan.planned_date == planned_date and plan.slot == 1 for plan in plans)
    assert all(plan.raw_md.count(DAILY_READING_AUTOMATION_MARKER) == 1 for plan in plans)
    assert all(plan.raw_md.endswith("> 自动创作，非真人阅读经历。") for plan in plans)
    assert [plan.scheduled_time for plan in plans] == list(DAILY_READING_SCHEDULED_TIMES)
    assert len(await service.plan_day(planned_date, force_local=True)) == 2
    assert daily_reading_seed_key(planned_date, 1) == "daily-reading:2026-11-15:01"
    assert plans[0].seed_key == "daily-reading:2026-11-15:1000:01"
    assert daily_reading_plan_key(planned_date) == "2026-11-15"
    assert daily_reading_plan_key(planned_date, scheduled_time="14:00") == "2026-11-15:1400"


def test_local_scheduled_reading_avoids_used_title_and_body() -> None:
    """已使用组合会被跳过，不能靠改标题重复当日正文。"""

    planned_date = date(2026, 11, 15)
    first = build_local_scheduled_reading_draft(planned_date, "10:00", [])
    second = build_local_scheduled_reading_draft(
        planned_date, "10:00", [first.title], recent_bodies=[first.raw_md]
    )
    third = build_local_scheduled_reading_draft(
        planned_date, "10:00", [], recent_bodies=[first.raw_md]
    )
    assert first.title != second.title
    assert first.raw_md != second.raw_md
    assert first.raw_md != third.raw_md


def test_provider_explicit_single_count_preserves_legacy_two_contract() -> None:
    """新时段只接受一篇；旧解析默认仍拒绝一篇，模型上下文含真实时段。"""

    body = "这是关于阅读和日常选择的原创感受。" * 15
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"posts": [{"title": "读后暂时留一个问题", "body": body}]},
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }
    assert (
        len(
            parse_daily_reading_provider_result(
                response, fallback_model="local", expected_count=1
            ).drafts
        )
        == 1
    )
    with pytest.raises(AppError):
        parse_daily_reading_provider_result(response, fallback_model="local")
    messages = build_daily_reading_messages(date(2026, 11, 15), [], scheduled_time="14:00")
    assert '"planned_date": "2026-11-15"' in messages[1]["content"]
    assert '"scheduled_time": "14:00"' in messages[1]["content"]
    assert '"required_count": 1' in messages[1]["content"]
    assert "本次只生成一篇" in messages[0]["content"]
    assert (
        build_daily_reading_messages(date(2026, 11, 15), [])[0]["content"]
        == DAILY_READING_SYSTEM_PROMPT
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "personal", "admin", "disabled", "wrong_email"])
async def test_scheduled_identity_checks_reject_without_account_writes(bad: str | None) -> None:
    """缺失、个人、管理、禁用或误邮箱账号不得被改写成专用身份。"""

    for service_type, username, email in (
        (DailyReadingService, DAILY_READING_USERNAME, DAILY_READING_EMAIL),
        (LivingForumService, "老槐", PERSONAS["老槐"].email),
    ):
        user = (
            None
            if bad is None
            else SimpleNamespace(
                username=username,
                email="wrong@example.invalid" if bad == "wrong_email" else email,
                role="admin" if bad == "admin" else "user",
                status="disabled" if bad == "disabled" else "active",
                is_persona=bad != "personal",
            )
        )
        session = SimpleNamespace(scalar=AsyncMock(return_value=user))
        service = service_type(cast(AsyncSession, session), settings())
        with pytest.raises(AppError):
            if isinstance(service, DailyReadingService):
                await service._require_scheduled_persona()
            else:
                await service._require_scheduled_persona("老槐")
        if user is not None:
            assert user.is_persona is (bad != "personal")
            assert user.role == ("admin" if bad == "admin" else "user")


@pytest.mark.asyncio
async def test_reading_scheduled_retry_does_not_regenerate_or_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一日期/时段已发布后只回读审计，不能重选内容。"""

    planned_date = date(2026, 11, 15)
    service = DailyReadingService(cast(AsyncSession, object()), settings())
    existing = DailyReadingPublishResult(
        seed_key=daily_reading_seed_key(planned_date, 1, scheduled_time="14:00"),
        slot=1,
        title="已经发过的题目",
        status="existing",
        topic_id="reading-1",
    )
    monkeypatch.setattr(service, "_existing_result", AsyncMock(return_value=existing))
    plan = AsyncMock()
    publish = AsyncMock()
    monkeypatch.setattr(service, "_stored_or_new_plans", plan)
    monkeypatch.setattr(service, "_publish_plan", publish)
    result = await service.publish_day(planned_date, scheduled_time="14:00", publish_mode="auto")
    assert result["results"][0]["status"] == "existing"
    plan.assert_not_awaited()
    publish.assert_not_awaited()
    with pytest.raises(ValueError):
        await service.publish_day(planned_date, scheduled_time="14:00", slots=(1,))


@pytest.mark.asyncio
async def test_reading_scheduled_mode_publishes_exactly_one_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """指定时段不会隐式执行旧两篇，也不会触发账号刷新。"""

    planned_date = date(2026, 11, 15)
    service = DailyReadingService(cast(AsyncSession, object()), settings())
    plans = await DailyReadingService(None, settings()).plan_day(
        planned_date, force_local=True, scheduled_time="18:00"
    )
    monkeypatch.setattr(service, "_existing_result", AsyncMock(return_value=None))
    stored = AsyncMock(return_value=plans)
    publish = AsyncMock(
        return_value=DailyReadingPublishResult(
            seed_key=plans[0].seed_key,
            slot=1,
            title=plans[0].title,
            status="created",
            topic_id="one",
        )
    )
    monkeypatch.setattr(service, "_stored_or_new_plans", stored)
    monkeypatch.setattr(service, "_publish_plan", publish)
    result = await service.publish_day(planned_date, scheduled_time="18:00", publish_mode="auto")
    stored.assert_awaited_once_with(planned_date, force_local=False, scheduled_time="18:00")
    publish.assert_awaited_once_with(plans[0])
    assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_stored_single_plan_replays_with_one_automation_marker() -> None:
    """已选稿重放不重复加标识，最大合法正文也能正常恢复。"""

    audit = SimpleNamespace(
        data={
            "posts": [{"title": "一个较长的读书题目", "raw_md": "文" * 800}],
            "model_name": "local",
            "provider_mode": "local_fallback",
        }
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=audit))
    service = DailyReadingService(cast(AsyncSession, session), settings())
    plans = await service._stored_plans(date(2026, 11, 15), scheduled_time="10:00")
    assert plans is not None and len(plans) == 1
    assert plans[0].raw_md.count(DAILY_READING_AUTOMATION_MARKER) == 1


@pytest.mark.asyncio
async def test_living_existing_audit_respects_moderation_without_topic_lookup() -> None:
    """新时段已发布即使被删帖也不重发，不查询或恢复历史帖子。"""

    session = SimpleNamespace(
        scalar=AsyncMock(return_value=SimpleNamespace(data={"topic_id": "deleted"}))
    )
    service = LivingForumService(cast(AsyncSession, session), settings())
    assert await service._existing_topic_id("slot", respect_moderation=True) == "deleted"


def test_scheduled_cli_rejects_legacy_slots_and_automatic_engagement() -> None:
    """新CLI不会混入旧双slot、首评或投票流程。"""

    assert parse_living_args(["--scheduled-time", "10:00"]).scheduled_time == "10:00"
    assert parse_reading_args(["--scheduled-time", "14:00"]).scheduled_time == "14:00"
    with pytest.raises(SystemExit):
        parse_living_args(["--scheduled-time", "10:00", "--engage"])
    with pytest.raises(SystemExit):
        parse_reading_args(["--scheduled-time", "14:00", "--slot", "1"])


@pytest.mark.asyncio
@pytest.mark.parametrize("recover", [False, True])
async def test_living_scheduled_write_uses_strict_identity_and_canonical_path(
    monkeypatch: pytest.MonkeyPatch, recover: bool
) -> None:
    """新稿走正规发帖；提交中断恢复不再发帖，始终不调用旧账号更新。"""

    session = SimpleNamespace(rollback=AsyncMock())
    service = LivingForumService(cast(AsyncSession, session), settings())
    plan = service.plan_day(date(2026, 11, 15), scheduled_time="10:00")[0]
    board, author, topic = (SimpleNamespace(id=value) for value in ("board", "author", "topic"))
    monkeypatch.setattr(service, "_existing_topic_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_find_public_board", AsyncMock(return_value=board))
    strict = AsyncMock(return_value=author)
    legacy = AsyncMock(side_effect=AssertionError("must not rewrite persona"))
    monkeypatch.setattr(service, "_require_scheduled_persona", strict)
    monkeypatch.setattr(service, "_ensure_persona", legacy)
    monkeypatch.setattr(
        service, "_matching_scheduled_topic", AsyncMock(return_value=topic if recover else None)
    )
    record = AsyncMock()
    monkeypatch.setattr(service, "_record_publish_audit", record)
    create = AsyncMock(return_value=topic)
    monkeypatch.setattr(
        living_module, "ForumService", lambda _session: SimpleNamespace(create_topic=create)
    )

    result = await service._publish_plan(plan)

    assert result.status == ("recovered" if recover else "created")
    strict.assert_awaited_once_with(plan.author)
    legacy.assert_not_awaited()
    record.assert_awaited_once_with(plan, topic, board.id, author.id)
    if recover:
        create.assert_not_awaited()
    else:
        assert create.await_count == 1
        assert create.await_args.args[0] == "lounge"
        assert create.await_args.args[1].poll is None


@pytest.mark.asyncio
@pytest.mark.parametrize("recover", [False, True])
async def test_reading_scheduled_write_uses_strict_identity_and_recovers(
    monkeypatch: pytest.MonkeyPatch, recover: bool
) -> None:
    """读书新模式不创建/改写账号；同稿发帖后的中断只补审计。"""

    session = SimpleNamespace(rollback=AsyncMock())
    service = DailyReadingService(cast(AsyncSession, session), settings())
    plan = (
        await DailyReadingService(None, settings()).plan_day(
            date(2026, 11, 15), force_local=True, scheduled_time="14:00"
        )
    )[0]
    board, author, topic = (SimpleNamespace(id=value) for value in ("board", "author", "topic"))
    monkeypatch.setattr(service, "_existing_result", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_find_public_reading_board", AsyncMock(return_value=board))
    strict = AsyncMock(return_value=author)
    legacy = AsyncMock(side_effect=AssertionError("must not rewrite persona"))
    monkeypatch.setattr(service, "_require_scheduled_persona", strict)
    monkeypatch.setattr(service, "_ensure_persona", legacy)
    monkeypatch.setattr(
        service, "_matching_untracked_topic", AsyncMock(return_value=topic if recover else None)
    )
    record = AsyncMock()
    monkeypatch.setattr(service, "_record_publish_audit", record)
    create = AsyncMock(return_value=topic)
    monkeypatch.setattr(
        reading_module, "ForumService", lambda _session: SimpleNamespace(create_topic=create)
    )

    result = await service._publish_plan(plan)

    assert result.status == ("recovered" if recover else "created")
    strict.assert_awaited_once_with()
    legacy.assert_not_awaited()
    record.assert_awaited_once_with(plan, topic, board, author)
    if recover:
        create.assert_not_awaited()
    else:
        assert create.await_count == 1
        assert create.await_args.args[0] == "reading"
        assert DAILY_READING_AUTOMATION_MARKER in create.await_args.args[1].raw_md


@pytest.mark.asyncio
async def test_scheduled_plan_storage_keeps_unmarked_source_and_replays_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """选稿审计保存原始正文；恢复时只加一次自动标识，正文长度约束不漂移。"""

    added = []
    session = SimpleNamespace(add=added.append, commit=AsyncMock())
    service = DailyReadingService(cast(AsyncSession, session), settings())
    planned_date = date(2026, 11, 15)
    original = await DailyReadingService(None, settings()).plan_day(
        planned_date, force_local=True, scheduled_time="18:00"
    )
    monkeypatch.setattr(service, "_stored_plans", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "plan_day", AsyncMock(return_value=original))
    selected = await service._stored_or_new_plans(
        planned_date, force_local=True, scheduled_time="18:00"
    )
    assert selected == original
    assert len(added) == 1
    assert added[0].target_id == "2026-11-15:1800"
    assert DAILY_READING_AUTOMATION_MARKER not in added[0].data["posts"][0]["raw_md"]
    replay_session = SimpleNamespace(scalar=AsyncMock(return_value=added[0]))
    replay = await DailyReadingService(
        cast(AsyncSession, replay_session), settings()
    )._stored_plans(planned_date, scheduled_time="18:00")
    assert replay == original
