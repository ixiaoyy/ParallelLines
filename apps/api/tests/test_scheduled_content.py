from __future__ import annotations

import hashlib
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
        "external_id": "story-1",
        "title": "A fresh model announcement",
        "url": "https://openai.com/index/story-1",
        "summary": "A short source summary.",
        "author_names": [],
        "published_at": SLOT - timedelta(hours=1),
        "raw_payload": {},
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
    assert content.source_key("https://openai.com/index/a?utm_source=x#top") == content.source_key(
        "https://openai.com/index/a/"
    )
    assert content.source_key("https://openai.com/index/a") != content.source_key(
        "https://openai.com/index/b"
    )


@pytest.mark.parametrize(
    "values",
    [
        {"published_at": None},
        {"published_at": SLOT - timedelta(days=3)},
        {"published_at": SLOT + timedelta(hours=1)},
        {"url": "http://openai.com/index/story"},
        {"url": "https://evil.example/story"},
        {"url": "https://user@openai.com/story"},
    ],
)
def test_source_cards_reject_undated_stale_or_unapproved_sources(values: dict[str, object]) -> None:
    assert (
        content.news_draft("news", "OpenAI", entry(**values), hosts=("openai.com",), now=SLOT)
        is None
    )


def test_source_card_keeps_attribution_and_short_excerpt_without_invented_analysis() -> None:
    result = content.news_draft(
        "news",
        "OpenAI",
        entry(summary="<p>" + "原文摘要" * 100 + "</p>"),
        hosts=("openai.com",),
        now=SLOT,
    )
    assert result is not None
    assert result.raw_md.startswith("[A fresh model announcement]")
    assert result.raw_md.endswith("> 自动整理，详见原文。\n")
    assert "https://openai.com/index/story-1" in result.raw_md
    assert len(result.raw_md.split("来源短摘：")[1].splitlines()[0].strip()) <= 200
    assert "来源：OpenAI · 原文时间：2026-11-15T09:00+08:00" in result.raw_md
    assert result.raw_md.index("来源短摘：") < result.raw_md.index("来源：OpenAI")
    assert result.event_key == hashlib.sha256(b"afreshmodelannouncement").hexdigest()
    assert "<p>" not in result.raw_md


@pytest.mark.parametrize("channel, prefix", [("news", "资讯速递"), ("sports", "体坛快讯")])
def test_news_and_sports_titles_remain_source_led_not_date_led(channel: str, prefix: str) -> None:
    result = content.news_draft(channel, "来源站", entry(), hosts=("openai.com",), now=SLOT)
    assert result is not None
    assert result.title == f"{prefix}｜A fresh model announcement"
    assert result.raw_md.endswith("> 自动整理，详见原文。\n")


def test_hot_search_duplicate_identity_ignores_rank_heat_and_time() -> None:
    topics = [
        {"title": "新的热搜", "rank": 1, "heat": 100, "url": "https://s.weibo.com/weibo?q=a"},
        {"title": "另一热搜", "rank": 2, "url": "https://s.weibo.com/weibo?q=b"},
    ]
    first = content.hot_search_draft({"topics": topics, "collected_at": "10:00"}, SLOT)
    second = content.hot_search_draft(
        {"topics": list(reversed(topics)), "collected_at": "14:00"}, SLOT.replace(hour=14)
    )
    assert first is not None and second is not None
    assert first.source_key == second.source_key
    assert first.raw_md.endswith("> 自动采集，仅反映热度，内容未核实。\n")
    assert first.event_key == second.event_key
    assert content.hot_search_draft({"topics": []}, SLOT) is None


def test_hot_search_title_highlights_real_ranked_topics_and_keeps_metadata_below_content() -> None:
    topics = [
        {"title": "第三个词条", "rank": 3, "url": "https://s.weibo.com/weibo?q=3"},
        {"title": "榜首词条", "rank": 1, "url": "https://s.weibo.com/weibo?q=1"},
        {"title": "第二个词条", "rank": 2, "url": "https://s.weibo.com/weibo?q=2"},
    ]
    result = content.hot_search_draft(
        {"topics": topics, "collected_at": "2026-11-15T10:01:00+08:00"}, SLOT
    )
    assert result is not None
    assert result.title == "微博热搜｜榜首词条、第二个词条"
    assert result.raw_md.startswith("3. [第三个词条](https://s.weibo.com/weibo?q=3)")
    assert "采集时间：2026-11-15T10:01:00+08:00" in result.raw_md
    assert "来源：[微博热搜榜](https://s.weibo.com/top/summary)" in result.raw_md
    assert result.raw_md.endswith("> 自动采集，仅反映热度，内容未核实。\n")
    assert result.raw_md.index("1. [榜首词条]") < result.raw_md.index("采集时间：")

    # 名次或标题展示变化不更换词条集合的幂等标识。
    reordered = [dict(topic, rank=4 - topic["rank"]) for topic in topics]
    other = content.hot_search_draft({"topics": reordered}, SLOT.replace(hour=14))
    assert other is not None and other.title != result.title
    assert other.source_key == result.source_key and other.event_key == result.event_key


class SessionDouble:
    """Expose only bounded scalar reads and explicit transaction outcomes for service tests."""

    def __init__(self, results: list[object]) -> None:
        self.scalar = AsyncMock(side_effect=results)
        self.scalars = AsyncMock(return_value=[])
        self.execute = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
        self.added: list[AuditLog] = []
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def add(self, record: AuditLog) -> None:
        self.added.append(record)


def actor(**overrides: object) -> SimpleNamespace:
    values = {
        "id": "1",
        "username": "小小资讯",
        "email": "xiaoxiao-zixun@pingxingxian.space",
        "role": "user",
        "status": "active",
        "is_persona": True,
        "persona_kind": "automation",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_publish_stages_slot_source_event_audits_before_canonical_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionDouble(
        [actor(), None, SimpleNamespace(id="2", visibility="public"), None, None]
    )
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))

    async def create(_service, board, payload, owner, **flags):
        assert board == "frontier" and owner.is_persona is True
        assert flags == {"skip_spam_checks": True, "skip_review_queue": True}
        assert {record.action for record in session.added} == {
            content.SLOT_ACTION,
            content.SOURCE_ACTION,
            content.EVENT_ACTION,
        }
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
@pytest.mark.parametrize(
    "values",
    [
        {"is_persona": False},
        {"persona_kind": None},
        {"role": "admin"},
        {"status": "disabled"},
        {"email": "someone@example.com"},
    ],
)
async def test_publish_refuses_wrong_identity_without_repair(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, object]
) -> None:
    owner = actor(**values)
    session = SessionDouble([owner])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([draft()], [])))
    with pytest.raises(PermissionDeniedError):
        await service.publish_slot("news", SLOT)
    assert session.added == []
    assert vars(owner) == vars(actor(**values))


@pytest.mark.asyncio
async def test_slot_receipt_prevents_republish_and_source_marker_skips_new_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    previous = SimpleNamespace(
        data={"source_url": "https://openai.com/index/a"},
        actor_id="1",
        board_id="2",
        created_at=SLOT,
    )
    with pytest.raises(ConflictError):
        await service._existing_result(previous, "news", "news:2026-11-15:10")
    assert not session.added


@pytest.mark.asyncio
async def test_hot_search_snapshots_are_per_slot_and_reused_on_retry(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(content.weibo, "DEFAULT_OUTPUT_DIR", tmp_path)
    def fetch(**_):
        return {"ok": 1, "data": {"realtime": [{"note": "新词条"}]}}
    monkeypatch.setattr(content.weibo, "fetch_hot_search_payload", fetch)
    service = content.ScheduledContentService(
        cast(AsyncSession, object()), Settings(_env_file=None)
    )
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


def test_hot_search_dedup_uses_only_valid_actually_rendered_top_ten() -> None:
    topics = [
        {"title": f"词条{index}", "rank": index + 1, "url": f"https://s.weibo.com/weibo?q={index}"}
        for index in range(11)
    ]
    first = content.hot_search_draft({"topics": topics}, SLOT)
    topics[-1]["title"] = "不显示的词条改变"
    second = content.hot_search_draft({"topics": topics}, SLOT.replace(hour=14))
    assert first.source_key == second.source_key
    assert (
        content.hot_search_draft(
            {"topics": [{"title": "无效", "url": "https://evil.example/"}]}, SLOT
        )
        is None
    )


def test_old_public_posts_with_canonical_source_are_not_republished() -> None:
    candidate = draft()
    assert content.draft_matches_recent(
        candidate, [("另一个标题", "原文：https://openai.com/index/story-1?utm_source=old")]
    )
    assert not content.draft_matches_recent(candidate, [("无关标题", "另一条消息")])


@pytest.mark.asyncio
async def test_all_source_connection_failures_are_not_successful_no_candidate(monkeypatch) -> None:
    service = content.ScheduledContentService(
        cast(AsyncSession, object()), Settings(_env_file=None)
    )
    monkeypatch.setattr(
        content._BoundedRssCollector, "_fetch_rss_entries", AsyncMock(side_effect=TimeoutError())
    )
    with pytest.raises(OSError):
        await service.publish_slot("news", SLOT)


@pytest.mark.asyncio
async def test_healthy_empty_feeds_are_a_real_no_candidate_not_failure(monkeypatch) -> None:
    service = content.ScheduledContentService(
        cast(AsyncSession, object()), Settings(_env_file=None)
    )
    monkeypatch.setattr(
        content._BoundedRssCollector, "_fetch_rss_entries", AsyncMock(return_value=[])
    )
    result = await service.publish_slot("news", SLOT)
    assert result["status"] == "no_candidate"
    assert result["source_errors"] == []


def social_draft(index: int = 0) -> content.SourcedDraft:
    """生成有独立原帖/文章身份的海外候选，无网络或数据库访问。"""

    return content.overseas_draft(content.overseas_content.SocialEntry(
        "Bluesky · GamingOnLinux", "@gamingonlinux.com", f"Game announcement {index}",
        f"https://bsky.app/profile/did:plc:example/post/post{index}", SLOT,
        f"https://www.gamingonlinux.com/2026/11/game{index}/",
    ))


def social_actor() -> SimpleNamespace:
    """沿用已存在的小瓜身份，不创建账号或提升角色。"""

    return actor(
        username="小瓜同学", email="xiaogua@pingxingxian.space", persona_kind="editorial"
    )


def test_overseas_digest_is_one_short_attributed_post_not_a_translated_article() -> None:
    entry = content.overseas_content.SocialEntry(
        "Bluesky · GamingOnLinux", "@gamingonlinux.com", "word " * 100 + "[bad](link)",
        "https://bsky.app/profile/did:plc:example/post/one", SLOT, None,
    )
    item = content.overseas_draft(entry)
    result = content.overseas_digest([item, social_draft(2)])
    assert result.title.startswith("海外动态｜") and len(result.title) <= 180
    headline = result.title.split("｜", 1)[1].split("、", 1)[0]
    assert headline.endswith("…") and set(headline.rstrip("…").split()) == {"word"}
    assert result.raw_md.startswith("1. [word ")
    assert result.raw_md.count("原文时间：") == 2
    assert "@gamingonlinux" in result.raw_md
    assert "2026-11-15T10:00+08:00" in result.raw_md
    assert result.source_url in result.raw_md
    assert len(item.title.split()) == 25
    assert "未经本站独立核实" in result.raw_md
    assert content.overseas_digest([social_draft(2), item]).source_key == result.source_key
    with pytest.raises(ValueError):
        content.overseas_digest([])
    with pytest.raises(ValueError):
        content.overseas_digest([social_draft(i) for i in range(6)])


def test_overseas_real_forum_renderer_keeps_all_links_and_literal_handles_without_escapes():
    from app.services.forum import render_markdown

    entries = [content.overseas_content.SocialEntry(
        "Mastodon · heise online", "@heiseonline", "Strahlenschützer " * 20 + " [unsafe](https://evil.example)",
        f"https://social.heise.de/@heiseonline/{index}", SLOT, None,
    ) for index in range(5)]
    items = [content.overseas_draft(entry) for entry in entries]
    cooked = render_markdown(content.overseas_digest(items).raw_md)
    assert cooked.count('<a href="https://social.heise.de/@heiseonline/') == 5
    assert "https://evil.example" not in cooked
    assert "\\" not in cooked and "&gt; 自动收集" not in cooked
    assert all(len(item.title) <= 150 for item in items)
    assert "@heiseonline" in cooked and "Strahlenschützer" in cooked


@pytest.mark.asyncio
async def test_overseas_publication_dedups_items_in_one_bounded_query_before_atomic_commit(
    monkeypatch,
) -> None:
    drafts = [social_draft(index) for index in range(8)]
    # 重复原帖/同文章跨平台、历史原帖和已有文章事件均不得挤占新合集。
    cross_post = content.SourcedDraft(
        "Cross post", "Cross-post body", "Mastodon", "https://mastodon.social/@g/1",
        "other-post-key", drafts[0].event_key,
    )
    session = SessionDouble(
        [social_actor(), None, SimpleNamespace(id="lounge", visibility="public")]
    )
    known = [
        (content.SOURCE_ACTION, drafts[1].source_key),
        (content.EVENT_ACTION, drafts[2].event_key),
    ]
    recent = [("旧合集", f"[旧原帖]({drafts[3].source_url})")]
    session.execute.side_effect = [
        SimpleNamespace(all=lambda: recent), SimpleNamespace(all=lambda: known),
    ]
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=(
        [drafts[0], cross_post, *drafts[1:]], ["heise online: TimeoutError"]
    )))

    calls = []

    async def create(_service, board, payload, owner, **flags):
        calls.append(payload)
        assert board == "lounge" and owner.username == "小瓜同学"
        assert payload.tags == ["海外动态"]
        assert payload.raw_md.count("原文时间：") == 5
        assert "Cross-post body" not in payload.raw_md
        for old in drafts[1:4]:
            assert old.source_url not in payload.raw_md
        assert len(session.added) == 11
        assert all("topic_id" not in record.data for record in session.added)
        for item in [drafts[0], *drafts[4:]]:
            marker = next(record for record in session.added if (
                record.action == content.SOURCE_ACTION and record.target_id == item.source_key
            ))
            assert marker.data["source_url"] == item.source_url
        return SimpleNamespace(id="digest-1", title=payload.title)

    monkeypatch.setattr(content.ForumService, "create_topic", create)
    result = await service.publish_slot("overseas", SLOT)
    assert result["status"] == "published" and result["topic_id"] == "digest-1"
    assert result["source_errors"] == ["heise online: TimeoutError"]
    assert len(calls) == 1
    assert session.execute.await_count == 2
    batch_query = str(session.execute.await_args_list[1].args[0])
    assert "DISTINCT" in batch_query and " IN " in batch_query
    assert all(record.data["topic_id"] == "digest-1" for record in session.added)
    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_overseas_preview_does_not_lock_or_write_and_does_not_pad_with_old_posts(monkeypatch):
    old, new = social_draft(0), social_draft(1)
    session = SessionDouble(
        [social_actor(), None, SimpleNamespace(id="lounge", visibility="public")]
    )
    session.execute.side_effect = [
        SimpleNamespace(all=lambda: []),
        SimpleNamespace(all=lambda: [(content.SOURCE_ACTION, old.source_key)]),
    ]
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([old, new], [])))
    result = await service.publish_slot("overseas", SLOT, dry_run=True)
    assert result["status"] == "preview" and result["author"] == "小瓜同学"
    assert new.source_url in result["raw_md"] and old.source_url not in result["raw_md"]
    assert result["raw_md"].count("原文时间：") == 1
    assert "FOR UPDATE" not in str(session.scalar.await_args_list[0].args[0])
    assert session.added == []
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_overseas_slot_receipt_and_item_audits_both_prevent_republication(monkeypatch):
    item = social_draft()
    previous = SimpleNamespace(data={"topic_id": "existing-digest"})
    session = SessionDouble([social_actor(), previous])
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([item], [])))
    result = await service.publish_slot("overseas", SLOT)
    assert result["status"] == "already_published"
    assert result["topic_id"] == "existing-digest"
    assert session.added == []
    session.execute.assert_not_awaited()

    session = SessionDouble(
        [social_actor(), None, SimpleNamespace(id="lounge", visibility="public")]
    )
    session.execute.side_effect = [
        SimpleNamespace(all=lambda: []),
        SimpleNamespace(all=lambda: [(content.SOURCE_ACTION, item.source_key)]),
    ]
    service = content.ScheduledContentService(cast(AsyncSession, session), Settings(_env_file=None))
    monkeypatch.setattr(service, "_collect_drafts", AsyncMock(return_value=([item], [])))
    result = await service.publish_slot("overseas", SLOT.replace(hour=14))
    assert result["reason"] == "all_sources_or_events_already_published"
    assert session.added == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_overseas_collector_is_wired_without_opening_a_transaction(monkeypatch):
    entry = content.overseas_content.SocialEntry(
        "Mastodon · heise online", "@heiseonline", "Original German text",
        "https://social.heise.de/@heiseonline/123", SLOT, None,
    )
    collect = AsyncMock(return_value=([entry], []))
    monkeypatch.setattr(content.overseas_content, "collect_entries", collect)
    service = content.ScheduledContentService(
        cast(AsyncSession, object()), Settings(_env_file=None)
    )
    drafts, errors = await service._collect_drafts("overseas", SLOT, persist=False)
    assert drafts[0].source_url == entry.url and errors == []
    collect.assert_awaited_once_with(content.read_feed)
