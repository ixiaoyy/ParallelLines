from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utcnow
from app.models.news import FrontierNewsItem, FrontierNewsSource
from app.services.forum import render_markdown
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


def test_frontier_news_flash_markdown_starts_with_original_source() -> None:
    """Verify flash-news drafts render as source cards with optional image and summary."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    source = FrontierNewsSource(
        key="huggingface_blog",
        name="Hugging Face Blog",
        kind="rss",
        url="https://huggingface.co/blog/feed.xml",
        config={},
        enabled=True,
        trust_level=80,
        fetch_interval_minutes=240,
    )
    item = FrontierNewsItem(
        source_id="1",
        source=source,
        external_id="entry-1",
        canonical_url="https://huggingface.co/blog/example",
        canonical_url_hash="entry-1-hash",
        title="Example AI Agent Release",
        summary="The upstream post introduces a local AI agent workflow for developers.",
        author_names=["Hugging Face"],
        published_at=utcnow(),
        raw_payload={"image_url": "https://example.com/card.png"},
        item_type="news",
        suggested_tags=["智能体"],
        ai_title_zh="【动态】Example AI Agent Release",
        ai_summary_zh="这条资讯介绍了一个面向开发者的本地 AI 智能体工作流。",
        ai_key_points=["它关注本地执行智能体任务。", "它适合关注开发者工具的人阅读。"],
        ai_risk_flags=[],
        score=80,
        status="review_pending",
    )

    raw_md = service._build_topic_markdown(item)
    cooked_html = render_markdown(raw_md)
    tags = service._topic_tags(item)

    assert raw_md.startswith(":::news-card\n来源：Hugging Face Blog")
    assert "![Example AI Agent Release](https://example.com/card.png)" in raw_md
    assert "[Example AI Agent Release](https://huggingface.co/blog/example)" in raw_md
    assert "来源：Hugging Face Blog" in raw_md
    assert "这条资讯介绍了一个面向开发者的本地 AI 智能体工作流" in raw_md
    assert 'class="markdown-news-card"' in cooked_html
    assert '<img src="https://example.com/card.png"' in cooked_html
    assert "一句话：" not in raw_md
    assert "要点：" not in raw_md
    assert "可以关注：" not in raw_md
    assert "转载" not in raw_md
    assert "转载" not in tags


def test_frontier_news_card_markdown_keeps_title_and_summary_without_image() -> None:
    """Verify source cards degrade to title and summary when no image is available."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    source = FrontierNewsSource(
        key="hacker_news_ai",
        name="Hacker News AI 热点",
        kind="hacker_news",
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        config={},
        enabled=True,
        trust_level=65,
        fetch_interval_minutes=120,
    )
    item = FrontierNewsItem(
        source_id="1",
        source=source,
        external_id="entry-2",
        canonical_url="https://news.ycombinator.com/item?id=1",
        canonical_url_hash="entry-2-hash",
        title="AI agents discussion",
        summary=None,
        author_names=[],
        raw_payload={},
        item_type="discussion",
        suggested_tags=["智能体"],
        ai_title_zh="【社区】AI agents discussion",
        ai_summary_zh=None,
        ai_key_points=[],
        ai_risk_flags=[],
        score=65,
        status="review_pending",
    )

    raw_md = service._build_topic_markdown(item)
    cooked_html = render_markdown(raw_md)

    assert "![AI agents discussion]" not in raw_md
    assert "[AI agents discussion](https://news.ycombinator.com/item?id=1)" in raw_md
    assert "核心关键词是智能体/Agent" in raw_md
    assert 'markdown-news-card__body--text-only' in cooked_html
