from datetime import date
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError
from app.models.moderation import AuditLog
from app.models.user import User
from app.services.frontier_news import (
    DAILY_NEWS_AUDIT_ACTION,
    HOT_NEWS_BOARD_DESCRIPTION,
    LEGACY_HOT_NEWS_BOARD_DESCRIPTION,
    FrontierNewsService,
)
from app.services.moderation import ModerationService
from app.workers import background_jobs


class _SessionDouble:
    """Minimal async session double for daily publishing orchestration tests."""

    def __init__(self, scalar_result: object | None = None) -> None:
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0

    async def scalar(self, _statement: object) -> object | None:
        return self.scalar_result

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def test_daily_forum_defaults_are_one_topic_and_no_replies() -> None:
    """The legacy admin fields must reflect the new one-source-post daily policy."""

    assert Settings.model_fields["living_forum_daily_topic_limit"].default == 1
    assert Settings.model_fields["living_forum_daily_reply_limit"].default == 0


@pytest.mark.asyncio
async def test_frontier_board_replaces_the_old_manual_review_description() -> None:
    """The existing default board copy must describe the new daily source policy."""

    board = SimpleNamespace(
        name="热点资讯",
        description=LEGACY_HOT_NEWS_BOARD_DESCRIPTION,
    )
    session = _SessionDouble(board)
    service = FrontierNewsService(
        cast(AsyncSession, session),
        Settings(_env_file=None),
    )

    assert await service.ensure_frontier_board() is board
    assert board.description == HOT_NEWS_BOARD_DESCRIPTION


@pytest.mark.asyncio
async def test_daily_worker_uses_source_news_and_never_living_templates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scheduled job must collect news and invoke one daily candidate selection."""

    calls: list[tuple[str, object]] = []

    class _CollectionResult:
        def model_dump(self) -> dict[str, object]:
            return {"queued_count": 2}

    class _NewsService:
        def __init__(self, session: AsyncSession, settings: Settings) -> None:
            calls.append(("init", (session, settings.living_forum_publish_mode)))

        async def collect_due_sources(self) -> _CollectionResult:
            calls.append(("collect", None))
            return _CollectionResult()

        async def publish_daily_candidate(self, *, dry_run: bool) -> dict[str, object]:
            calls.append(("publish", dry_run))
            return {"status": "published", "topic_id": "101"}

    settings = Settings(_env_file=None, living_forum_publish_mode="auto")
    monkeypatch.setattr(background_jobs, "get_settings", lambda: settings)
    monkeypatch.setattr(background_jobs, "FrontierNewsService", _NewsService)

    session = cast(AsyncSession, object())
    result = await background_jobs.handle_publish_living_forum_day(session, {})

    assert not hasattr(background_jobs, "LivingForumService")
    assert calls == [
        ("init", (session, "auto")),
        ("collect", None),
        ("publish", False),
    ]
    assert result == {
        "collection": {"queued_count": 2},
        "publish": {"status": "published", "topic_id": "101"},
        "engagement": {"status": "disabled"},
    }


@pytest.mark.asyncio
async def test_daily_publish_stops_after_the_day_has_an_audit_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry on the same Shanghai date must not choose a second news item."""

    existing = SimpleNamespace(
        data={"item_id": "31", "topic_id": "41"},
    )
    session = _SessionDouble(existing)
    service = FrontierNewsService(
        cast(AsyncSession, session),
        Settings(_env_file=None),
    )
    candidate_lookup = AsyncMock()
    monkeypatch.setattr(service, "_daily_news_candidate", candidate_lookup)

    result = await service.publish_daily_candidate(planned_date=date(2026, 7, 17))

    assert result == {
        "status": "already_published",
        "publish_date": "2026-07-17",
        "item_id": "31",
        "topic_id": "41",
    }
    candidate_lookup.assert_not_awaited()
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_daily_publish_approves_one_fresh_source_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh candidate should use the moderation pipeline and write the day audit."""

    session = _SessionDouble()
    service = FrontierNewsService(
        cast(AsyncSession, session),
        Settings(_env_file=None),
    )
    reviewable = SimpleNamespace(id="71", topic_id=None, board_id="5")
    candidate = SimpleNamespace(
        id="61",
        title="Original headline",
        ai_title_zh="当天热点",
        canonical_url="https://news.example.com/story-61",
        source=SimpleNamespace(name="Example News"),
        reviewable_id=reviewable.id,
        reviewable=reviewable,
    )
    bot = SimpleNamespace(id="51", is_persona=True)
    monkeypatch.setattr(
        service,
        "_daily_news_candidate",
        AsyncMock(return_value=candidate),
    )
    monkeypatch.setattr(service, "ensure_bot_user", AsyncMock(return_value=bot))

    async def approve(
        _moderation: ModerationService,
        reviewable_id: str,
        actor: object,
    ) -> object:
        assert reviewable_id == reviewable.id
        assert actor is bot
        reviewable.topic_id = "81"
        return reviewable

    monkeypatch.setattr(
        ModerationService,
        "auto_approve_frontier_news_reviewable",
        approve,
    )

    result = await service.publish_daily_candidate(planned_date=date(2026, 7, 17))

    assert result == {
        "status": "published",
        "topic_id": "81",
        "publish_date": "2026-07-17",
        "item_id": "61",
        "title": "当天热点",
        "source_name": "Example News",
        "source_url": "https://news.example.com/story-61",
    }
    assert session.commit_count == 1
    audit = next(value for value in session.added if isinstance(value, AuditLog))
    assert audit.action == DAILY_NEWS_AUDIT_ACTION
    assert audit.target_id == "2026-07-17"
    assert audit.data["topic_id"] == "81"


@pytest.mark.asyncio
async def test_frontier_auto_approval_requires_the_draft_persona_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The internal bypass must reject any actor other than the news persona owner."""

    reviewable = SimpleNamespace(
        id="91",
        source="frontier_news",
        type="queued_topic",
        status="pending",
        created_by_id="11",
        data={"frontier_news_item_id": "12"},
    )
    session = _SessionDouble(reviewable)
    service = ModerationService(cast(AsyncSession, session))
    apply_decision = AsyncMock(return_value=reviewable)
    monkeypatch.setattr(
        service,
        "_apply_open_reviewable_decision_in_session",
        apply_decision,
    )

    with pytest.raises(PermissionDeniedError):
        await service.auto_approve_frontier_news_reviewable(
            reviewable.id,
            cast(User, SimpleNamespace(id="22", is_persona=True)),
        )

    actor = SimpleNamespace(id="11", is_persona=True)
    assert (
        await service.auto_approve_frontier_news_reviewable(
            reviewable.id,
            cast(User, actor),
        )
        is reviewable
    )
    payload = apply_decision.await_args.args[1]
    assert payload.action == "approve"
