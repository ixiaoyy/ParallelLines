from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.db.base import SHANGHAI_TZ
from app.models.moderation import AuditLog
from app.services import scheduled_content as content
from app.services.frontier_news import FetchedNewsEntry

SLOT = datetime(2026, 11, 15, 10, tzinfo=SHANGHAI_TZ)


def entry(**overrides: object) -> FetchedNewsEntry:
    """Build one dated source entry without network or database access."""

    values = {
        "external_id": "story-1", "title": "A fresh model announcement",
        "url": "https://openai.com/index/story-1", "summary": "A short source summary.",
        "author_names": [], "published_at": SLOT - timedelta(hours=1), "raw_payload": {},
    }
    values.update(overrides)
    return FetchedNewsEntry(**values)


def draft() -> content.SourcedDraft:
    """Return a valid source card fixture with stable duplicate markers."""

    result = content.news_draft("news", "OpenAI", entry(), hosts=("openai.com",), now=SLOT)
    assert result is not None
    return result


def test_slots_are_aware_and_exactly_three_shanghai_hours() -> None:
    assert content.slot_identity("news", SLOT)[1] == "news:2026-11-15:10"
    for value in (SLOT.replace(tzinfo=None), SLOT.replace(hour=9), SLOT.replace(minute=1)):
        with pytest.raises(ValueError):
            content.slot_identity("news", value)
    with pytest.raises(ValueError):
        content.slot_identity("unknown", SLOT)


def test_source_identity_ignores_tracking_but_preserves_article_identity() -> None:
    assert content.source_key("https://openai.com/index/a?utm_source=x#top") == content.source_key("https://openai.com/index/a/")
    assert content.source_key("https://openai.com/index/a") != content.source_key("https://openai.com/index/b")


@pytest.mark.parametrize("values", [
    {"published_at": None}, {"published_at": SLOT - timedelta(days=3)},
    {"published_at": SLOT + timedelta(hours=1)},
    {"url": "http://openai.com/index/story"},
    {"url": "https://evil.example/story"},
    {"url": "https://user@openai.com/story"},
])
def test_source_cards_reject_undated_stale_or_unapproved_sources(values: dict[str, object]) -> None:
    assert content.news_draft("news", "OpenAI", entry(**values), hosts=("openai.com",), now=SLOT) is None


def test_source_card_keeps_attribution_and_short_excerpt_without_invented_analysis() -> None:
    result = content.news_draft("news", "OpenAI", entry(summary="<p>" + "原文摘要" * 100 + "</p>"), hosts=("openai.com",), now=SLOT)
    assert result is not None
    assert "专用运营身份自动采集" in result.raw_md
    assert "https://openai.com/index/story-1" in result.raw_md
    assert len(result.raw_md.split("来源短摘：")[1].strip()) <= 200
    assert "<p>" not in result.raw_md


def test_hot_search_duplicate_identity_ignores_rank_heat_and_time() -> None:
    topics = [{"title": "新的热搜", "rank": 1, "heat": 100, "url": "https://s.weibo.com/weibo?q=a"}, {"title": "另一热搜", "rank": 2, "url": "https://s.weibo.com/weibo?q=b"}]
    first = content.hot_search_draft({"topics": topics, "collected_at": "10:00"}, SLOT)
    second = content.hot_search_draft({"topics": list(reversed(topics)), "collected_at": "14:00"}, SLOT.replace(hour=14))
    assert first is not None and second is not None
    assert first.source_key == second.source_key
    assert "不代表相关说法已核实" in first.raw_md
    assert first.event_key == second.event_key
    assert content.hot_search_draft({"topics": []}, SLOT) is None


class SessionDouble:
    """Expose only bounded scalar reads and explicit transaction outcomes for service tests."""

    def __init__(self, results: list[object]) -> None:
        self.scalar = AsyncMock(side_effect=results)
        self.scalars = AsyncMock(return_value=[])
        self.added: list[AuditLog] = []
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def add(self, record: AuditLog) -> None:
        self.added.append(record)


def actor(**overrides: object) -> SimpleNamespace:
    values = {"id": "1", "username": "小小资讯", "email": "xiaoxiao-zixun@pingxingxian.space", "role": "user", "status": "active", "is_persona": True, "persona_kind": "automation"}
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_publish_stages_slot_source_event_audits_before_canonical_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SessionDouble([actor(), None, SimpleNamespace(id="2", visibility="public"), None, None])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))

    async def create(_service, board, payload, owner, **flags):
        assert board == "frontier" and owner.is_persona is True
        assert flags == {"skip_spam_checks": True, "skip_review_queue": True}
        assert {record.action for record in session.added} == {content.SLOT_ACTION, content.SOURCE_ACTION, content.EVENT_ACTION}
        assert all("topic_id" not in record.data for record in session.added)
        return SimpleNamespace(id="3", title=payload.title)

    monkeypatch.setattr(content.ForumService, "create_topic", create)
    result = await service.publish_slot("news", SLOT)
    assert result["status"] == "published" and result["topic_id"] == "3"
    assert all(record.data["topic_id"] == "3" for record in session.added)
    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()
    assert "FOR UPDATE" in str(session.scalar.await_args_list[0].args[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [{"is_persona": False}, {"persona_kind": None}, {"role": "admin"}, {"status": "disabled"}, {"email": "someone@example.com"}])
async def test_publish_refuses_wrong_identity_without_repair(monkeypatch: pytest.MonkeyPatch, values: dict[str, object]) -> None:
    owner = actor(**values)
    session = SessionDouble([owner])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))
    with pytest.raises(PermissionDeniedError):
        await service.publish_slot("news", SLOT)
    assert session.added == []
    assert vars(owner) == vars(actor(**values))


@pytest.mark.asyncio
async def test_slot_receipt_prevents_republish_and_source_marker_skips_new_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = SimpleNamespace(data={"topic_id": "old"})
    session = SessionDouble([actor(), previous])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))
    assert (await service.publish_slot("news", SLOT))["status"] == "already_published"
    assert not session.added
    session = SessionDouble([actor(), None, SimpleNamespace(id="2", visibility="public"), previous])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))
    result = await service.publish_slot("news", SLOT.replace(hour=14))
    assert result["reason"] == "all_sources_or_events_already_published"
    assert not session.added


@pytest.mark.asyncio
async def test_missing_receipt_never_blindly_publishes_again() -> None:
    session = SessionDouble([])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    previous = SimpleNamespace(data={"source_url": "https://openai.com/index/a"}, actor_id="1", board_id="2", created_at=SLOT)
    with pytest.raises(ConflictError):
        await service._existing_result(previous, "news", "news:2026-11-15:10")
    assert not session.added


@pytest.mark.asyncio
async def test_hot_search_snapshots_are_per_slot_and_reused_on_retry(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content.weibo, "DEFAULT_OUTPUT_DIR", tmp_path)
    fetch = lambda **_: {"ok": 1, "data": {"realtime": [{"note": "新词条"}]}}
    monkeypatch.setattr(content.weibo, "fetch_hot_search_payload", fetch)
    service = content.ScheduledContentService(cast(AsyncSession, object()), Settings(_env_file=None))
    first = await service.collect_hot_search(SLOT)
    assert first == await service.collect_hot_search(SLOT)
    await service.collect_hot_search(SLOT.replace(hour=14))
    assert (tmp_path / "2026-11-15" / "10.json").exists()
    assert (tmp_path / "2026-11-15" / "14.json").exists()


def test_weibo_response_size_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

    payload = json.dumps({"ok": 1, "data": {"realtime": []}}).encode()
    monkeypatch.setattr(content.weibo, "urlopen", lambda *args, **kwargs: Response(payload))
    assert content.weibo.fetch_hot_search_payload(timeout=1)["ok"] == 1
    monkeypatch.setattr(content.weibo, "MAX_RESPONSE_BYTES", 4)
    with pytest.raises(RuntimeError, match="size limit"):
        content.weibo.fetch_hot_search_payload(timeout=1)
