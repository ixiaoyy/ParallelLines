"""海外公开来源的离线回归；所有网络响应为 fixture，不连接数据库。"""

from __future__ import annotations

import io
import json
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.core.exceptions import ValidationError
from app.db.base import SHANGHAI_TZ
from app.services import overseas_content as social
from app.services import scheduled_content as content

NOW = datetime(2026, 11, 17, 10, tzinfo=SHANGHAI_TZ)
ARTICLE = "https://www.gamingonlinux.com/2026/11/a-real-story/"


def bluesky_payload(source=social.SOURCES[1]) -> dict:
    """模拟官方 feed 结构，保留独立 DID、原帖 URI 和文章卡片。"""

    return {
        "feed": [
            {
                "post": {
                    "uri": f"at://{source.actor_id}/app.bsky.feed.post/3example",
                    "author": {"did": source.actor_id, "handle": source.handle, "labels": []},
                    "record": {
                        "$type": "app.bsky.feed.post",
                        "text": "A new Linux game is available.",
                        "createdAt": "2026-11-17T01:00:00Z",
                    },
                    "labels": [],
                    "embed": {
                        "$type": "app.bsky.embed.external#view",
                        "external": {"uri": ARTICLE},
                    },
                }
            }
        ]
    }


def mastodon_payload(source=social.SOURCES[2]) -> list:
    """模拟自有实例账号的公开原创状态；回复、转发及敏感字段显式存在。"""

    return [
        {
            "id": "12345",
            "url": f"{source.profile_url}/12345",
            "account": {"id": source.actor_id, "acct": source.handle},
            "visibility": "public",
            "sensitive": False,
            "spoiler_text": "",
            "in_reply_to_id": None,
            "reblog": None,
            "quote": None,
            "created_at": "2026-11-17T09:00:00+08:00",
            "content": '<p>A new Linux game &amp; update.</p><p><a href="'
            + ARTICLE
            + '">Read more</a></p>',
            "card": {"url": ARTICLE},
        }
    ]


def empty_reader(url: str) -> str:
    """各白名单地址返回健康但为空的响应，未知地址直接让测试失败。"""

    source = next(source for source in social.SOURCES if source.url == url)
    return json.dumps({"feed": []} if source.platform == "bluesky" else [])


def test_fixed_inventory_has_two_platforms_and_four_account_bound_endpoints() -> None:
    assert [source.platform for source in social.SOURCES] == [
        "bluesky",
        "bluesky",
        "mastodon",
        "mastodon",
    ]
    assert len({source.url for source in social.SOURCES}) == 4
    assert all("limit=5" in source.url for source in social.SOURCES)


def test_public_originals_keep_source_author_time_text_and_post_url() -> None:
    bsky = social.parse_entries(social.SOURCES[1], bluesky_payload(), now=NOW)[0]
    mastodon = social.parse_entries(social.SOURCES[2], mastodon_payload(), now=NOW)[0]
    assert bsky.published_at == mastodon.published_at
    assert bsky.author == "@gamingonlinux.com"
    assert bsky.url == f"https://bsky.app/profile/{social.SOURCES[1].actor_id}/post/3example"
    assert mastodon.url == "https://mastodon.social/@gamingonlinux/12345"
    assert mastodon.text == "A new Linux game & update. Read more"
    assert bsky.article_url == mastodon.article_url == ARTICLE
    assert bsky.source_name.startswith("Bluesky") and mastodon.source_name.startswith("Mastodon")


@pytest.mark.parametrize(
    "field,value",
    [
        ("createdAt", None),
        ("createdAt", "not-a-date"),
        ("createdAt", "2026-11-17T09:00:00"),
        ("createdAt", "2026-11-14T09:00:00+08:00"),
        ("createdAt", "2026-11-17T11:00:00+08:00"),
        ("text", ""),
    ],
)
def test_bluesky_rejects_undated_stale_future_or_empty_posts(field, value) -> None:
    payload = bluesky_payload()
    payload["feed"][0]["post"]["record"][field] = value
    assert social.parse_entries(social.SOURCES[1], payload, now=NOW) == []


@pytest.mark.parametrize(
    "location,field,value",
    [
        ("row", "reason", {"$type": "app.bsky.feed.defs#reasonRepost"}),
        ("record", "reply", {"parent": {"uri": "at://other/post"}}),
        ("record", "labels", {"values": [{"val": "porn"}]}),
        ("post", "labels", [{"val": "sexual"}]),
        ("author", "labels", [{"val": "spam"}]),
        ("post", "embed", {"$type": "app.bsky.embed.record#view"}),
        ("post", "embed", {"$type": "app.bsky.embed.recordWithMedia#view"}),
        ("post", "uri", "at://did:plc:someoneelse/app.bsky.feed.post/123"),
    ],
)
def test_bluesky_excludes_replies_reposts_quotes_labels_and_foreign_post_ids(
    location, field, value
):
    payload = bluesky_payload()
    row = payload["feed"][0]
    target = row if location == "row" else row["post"]
    if location in ("record", "author"):
        target = target[location]
    target[field] = value
    assert social.parse_entries(social.SOURCES[1], payload, now=NOW) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("visibility", "unlisted"),
        ("visibility", "private"),
        ("visibility", "direct"),
        ("sensitive", True),
        ("sensitive", None),
        ("spoiler_text", "Content warning"),
        ("in_reply_to_id", "1"),
        ("reblog", {"id": "1"}),
        ("quote", {"id": "1"}),
        ("url", "https://evil.example/12345"),
        ("id", "123/evil"),
        ("created_at", "2026-11-13T01:00:00Z"),
        ("created_at", "2026-11-17T11:00:00+08:00"),
    ],
)
def test_mastodon_excludes_nonpublic_sensitive_reply_repost_quote_and_invalid_posts(field, value):
    payload = mastodon_payload()
    payload[0][field] = value
    assert social.parse_entries(social.SOURCES[2], payload, now=NOW) == []


@pytest.mark.parametrize("platform", ("bluesky", "mastodon"))
def test_account_identity_drift_fails_that_source(platform) -> None:
    if platform == "bluesky":
        source, payload = social.SOURCES[1], bluesky_payload()
        payload["feed"][0]["post"]["author"]["did"] = "did:plc:unexpected"
    else:
        source, payload = social.SOURCES[2], mastodon_payload()
        payload[0]["account"]["id"] = "unrelated-account"
    with pytest.raises(ValueError, match="author_changed"):
        social.parse_entries(source, payload, now=NOW)


def test_source_item_cap_and_timezone_sort_do_not_depend_on_lexical_dates() -> None:
    payload = bluesky_payload()
    base = payload["feed"][0]
    payload["feed"] = [deepcopy(base) for _ in range(7)]
    for index, row in enumerate(payload["feed"]):
        row["post"]["record"]["createdAt"] = (NOW - timedelta(hours=index)).isoformat()
    payload["feed"][1]["post"]["record"]["createdAt"] = "2026-11-17T01:30:00Z"
    entries = social.parse_entries(social.SOURCES[1], payload, now=NOW)
    assert len(entries) == 5
    assert entries[0].published_at == NOW
    assert entries[1].published_at.hour == 1


def test_cross_platform_article_dedup_ignores_www_tracking_and_fragment() -> None:
    bsky = bluesky_payload()
    mastodon = mastodon_payload()
    mastodon[0]["card"]["url"] = ARTICLE.replace("www.", "") + "?utm_source=mastodon#comments"
    first = content.overseas_draft(social.parse_entries(social.SOURCES[1], bsky, now=NOW)[0])
    second = content.overseas_draft(social.parse_entries(social.SOURCES[2], mastodon, now=NOW)[0])
    assert first.source_key != second.source_key
    assert first.event_key == second.event_key


def test_bluesky_facet_link_without_external_card_still_dedups_cross_platform() -> None:
    payload = bluesky_payload()
    post = payload["feed"][0]["post"]
    del post["embed"]
    post["record"]["facets"] = [
        {
            "features": [
                {
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": ARTICLE,
                }
            ]
        }
    ]
    first = content.overseas_draft(social.parse_entries(social.SOURCES[1], payload, now=NOW)[0])
    second = content.overseas_draft(
        social.parse_entries(social.SOURCES[2], mastodon_payload(), now=NOW)[0]
    )
    assert first.event_key == second.event_key


def test_article_identity_uses_html_link_if_card_missing_but_ignores_unapproved_links() -> None:
    payload = mastodon_payload()
    payload[0]["card"] = None
    assert social.parse_entries(social.SOURCES[2], payload, now=NOW)[0].article_url == ARTICLE
    for url in (
        "https://evil.example/story",
        "https://www.gamingonlinux.com/",
        "javascript:alert(1)",
    ):
        payload[0]["content"] = '<p>Text <a href="' + url + '">link</a></p>'
        assert social.parse_entries(social.SOURCES[2], payload, now=NOW)[0].article_url is None


@pytest.mark.asyncio
async def test_collection_round_robins_accounts_and_preserves_partial_failure() -> None:
    def reader(url):
        source = next(source for source in social.SOURCES if source.url == url)
        if source is social.SOURCES[0]:
            raise TimeoutError("connection unavailable")
        payload = (
            bluesky_payload(source) if source.platform == "bluesky" else mastodon_payload(source)
        )
        return json.dumps(payload)

    entries, errors = await social.collect_entries(reader, now=NOW)
    assert [entry.source_name for entry in entries] == [
        source.name for source in social.SOURCES[1:]
    ]
    assert errors == ["Bluesky · Guardian US: TimeoutError"]


@pytest.mark.asyncio
async def test_healthy_empty_sources_are_no_candidate_with_no_errors() -> None:
    assert await social.collect_entries(empty_reader, now=NOW) == ([], [])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,expected",
    [
        (TimeoutError(), OSError),
        (HTTPError("https://public.example", 429, "limited", {}, None), OSError),
        (HTTPError("https://public.example", 403, "forbidden", {}, None), ValidationError),
        (ValueError("bad JSON"), ValidationError),
    ],
)
async def test_total_source_outage_is_not_reported_as_healthy_empty(error, expected) -> None:
    def reader(_):
        raise error

    with pytest.raises(expected):
        await social.collect_entries(reader, now=NOW)


@pytest.mark.asyncio
async def test_each_fetch_has_a_total_deadline(monkeypatch) -> None:
    async def slow_read(*args):
        import asyncio

        await asyncio.sleep(1)

    monkeypatch.setattr(social.asyncio, "to_thread", slow_read)
    monkeypatch.setattr(social, "TOTAL_TIMEOUT", 0.001)
    with pytest.raises(OSError):
        await social.collect_entries(empty_reader, now=NOW)


def test_transport_accepts_only_exact_configured_urls_and_bounds_bytes(monkeypatch) -> None:
    class Response(io.BytesIO):
        headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

    requests = []

    def open_response(request, **kwargs):
        requests.append(request)
        assert kwargs["timeout"] == 10.0
        return Response(b'{"feed":[]}')

    def opener(handler):
        assert handler.redirect_request(None, None, 302, "", {}, "https://evil.example") is None
        return SimpleNamespace(open=open_response)

    monkeypatch.setattr(content.urllib.request, "build_opener", opener)
    assert content.read_feed(social.SOURCES[0].url) == '{"feed":[]}'
    assert requests[-1].get_header("Accept") == "application/json"
    content.read_feed(content.FEEDS["news"][0][1])
    assert requests[-1].get_header("Accept") == "application/rss+xml, application/xml, text/xml"
    with pytest.raises(ValueError, match="未批准"):
        content.read_feed(social.SOURCES[0].url + "&cursor=unapproved")
    monkeypatch.setattr(content, "MAX_RESPONSE_BYTES", 4)
    with pytest.raises(ValueError, match="响应过大"):
        content.read_feed(social.SOURCES[0].url)
