from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.news import FrontierNewsItem, FrontierNewsSource
from app.services.frontier_news import DEFAULT_REVIEW_BATCH_SIZE, FrontierNewsService


def test_frontier_news_review_batch_size_defaults_and_bounds() -> None:
    """Verify per-source review batching defaults safely and clamps admin config values."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))

    default_source = FrontierNewsSource(
        key="default",
        name="Default Source",
        kind="rss",
        url="https://example.com/feed.xml",
        config={},
        enabled=True,
        trust_level=50,
        fetch_interval_minutes=60,
    )
    assert service._review_batch_size(default_source) == DEFAULT_REVIEW_BATCH_SIZE

    invalid_source = FrontierNewsSource(
        key="invalid",
        name="Invalid Source",
        kind="rss",
        url="https://example.com/feed.xml",
        config={"review_batch_size": "not-a-number"},
        enabled=True,
        trust_level=50,
        fetch_interval_minutes=60,
    )
    assert service._review_batch_size(invalid_source) == DEFAULT_REVIEW_BATCH_SIZE

    high_source = FrontierNewsSource(
        key="high",
        name="High Source",
        kind="rss",
        url="https://example.com/feed.xml",
        config={"review_batch_size": 99},
        enabled=True,
        trust_level=50,
        fetch_interval_minutes=60,
    )
    assert service._review_batch_size(high_source) == 10


def test_frontier_news_source_kind_drives_item_classification() -> None:
    """Verify source kind beats sparse title text when choosing reader-facing news type."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    expected_by_kind = {
        "arxiv": "paper",
        "github_search": "tool",
        "hacker_news": "discussion",
    }
    for kind, expected in expected_by_kind.items():
        source = FrontierNewsSource(
            key=f"{kind}_source",
            name=f"{kind} Source",
            kind=kind,
            url="https://example.com/source",
            config={},
            enabled=True,
            trust_level=50,
            fetch_interval_minutes=60,
        )
        item = FrontierNewsItem(
            source_id="1",
            source=source,
            external_id=f"{kind}:1",
            canonical_url=f"https://example.com/{kind}/1",
            canonical_url_hash=f"{kind}-hash",
            title="Sparse upstream title",
            summary=None,
            author_names=[],
            raw_payload={},
            item_type="news",
            suggested_tags=[],
            ai_key_points=[],
            ai_risk_flags=[],
            score=50,
            status="collected",
        )

        assert service._classify_item(item, item.title) == expected
