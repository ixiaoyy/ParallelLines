from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utcnow
from app.models.news import FrontierNewsItem, FrontierNewsSource
from app.services.forum import _topic_list_excerpt, render_markdown
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
        "xai_news": "news",
        "arena_leaderboard": "news",
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
        ai_summary_zh="一句话：这条资讯介绍了一个面向开发者的本地 AI 智能体工作流。",
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
    """Verify source cards degrade to text-only and avoid filler when no image is available."""

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
    assert "核心关键词" not in raw_md
    assert 'markdown-news-card__body--text-only' in cooked_html
    assert 'markdown-news-card__summary' not in cooked_html


def test_frontier_news_topic_excerpt_hides_internal_news_card_syntax() -> None:
    """Verify topic-list excerpts show readable summaries, not card control syntax."""

    raw_md = "\n".join(
        [
            ":::news-card",
            "来源：xAI News · 原文时间：2026-06-03 · 作者/来源账号：xAI",
            "![Grok Imagine 1.5 Preview](https://x.ai/images/news/grok.webp)",
            "[Grok Imagine 1.5 Preview](https://x.ai/news/grok-imagine-1-5)",
            "xAI 发布了新的图生视频模型，支持镜头运动、节奏、氛围和音效设计。",
            ":::",
        ]
    )

    excerpt = _topic_list_excerpt(raw_md)

    assert excerpt == "xAI 发布了新的图生视频模型，支持镜头运动、节奏、氛围和音效设计。"
    assert ":::news-card" not in excerpt
    assert "![" not in excerpt
    assert "来源：" not in excerpt


def test_frontier_news_card_image_uses_explicit_article_image_only() -> None:
    """Verify card images come from explicit article/feed image fields, not filler avatars."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    source = FrontierNewsSource(
        key="github_ai",
        name="GitHub AI",
        kind="github_search",
        url="https://api.github.com/search/repositories",
        config={},
        enabled=True,
        trust_level=70,
        fetch_interval_minutes=120,
    )
    avatar_only = FrontierNewsItem(
        source_id="1",
        source=source,
        external_id="repo-1",
        canonical_url="https://github.com/example/repo",
        canonical_url_hash="repo-1-hash",
        title="example/repo",
        summary="An AI repository",
        author_names=["example"],
        raw_payload={
            "owner": {"avatar_url": "https://avatars.githubusercontent.com/u/1?v=4"},
            "html_url": "https://github.com/example/repo",
        },
        item_type="tool",
        suggested_tags=[],
        ai_key_points=[],
        ai_risk_flags=[],
        score=70,
        status="review_pending",
    )
    with_og_image = FrontierNewsItem(
        source_id="2",
        source=source,
        external_id="article-1",
        canonical_url="https://example.com/article",
        canonical_url_hash="article-1-hash",
        title="Article with image",
        summary="An article with an explicit image",
        author_names=["Example"],
        raw_payload={"og_image": "https://example.com/news-card.webp"},
        item_type="news",
        suggested_tags=[],
        ai_key_points=[],
        ai_risk_flags=[],
        score=70,
        status="review_pending",
    )

    assert service._image_url(avatar_only) == ""
    assert service._image_url(with_og_image) == "https://example.com/news-card.webp"


@pytest.mark.asyncio
async def test_xai_news_fetcher_reads_official_video_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the xAI HTML source catches Grok Imagine style product launches."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    source = FrontierNewsSource(
        key="xai_news",
        name="xAI News",
        kind="xai_news",
        url="https://x.ai/news?category=all",
        config={"max_items": 4, "keywords": ["grok", "image-to-video"]},
        enabled=True,
        trust_level=95,
        fetch_interval_minutes=60,
    )
    detail_url = "https://x.ai/news/grok-imagine-1-5"

    async def fake_read_url(url: str) -> str:
        """Return deterministic xAI list/detail HTML for this parser test."""

        if url == source.url:
            return """
                <a href="/news/grok-imagine-1-5">Grok Imagine 1.5 Preview</a>
                <a href="/news/company-update">Company update</a>
            """
        if url == detail_url:
            return """
                <html>
                  <head>
                    <meta property="og:title" content="Grok Imagine 1.5 Preview | xAI" />
                    <meta property="og:description"
                      content="grok-imagine-video-1.5-preview is xAI's latest
                      image-to-video model." />
                    <meta property="og:image"
                      content="https://x.ai/images/news/grok-imagine-1-5-og.webp" />
                  </head>
                  <body><time datetime="2026-06-03T00:00:00+00:00"></time></body>
                </html>
            """
        return """
            <html><head><meta property="og:title" content="Company update | xAI" /></head></html>
        """

    monkeypatch.setattr(service, "_read_url", fake_read_url)

    entries = await service._fetch_xai_news_entries(source)

    assert len(entries) == 1
    assert entries[0].title == "Grok Imagine 1.5 Preview"
    assert entries[0].url == detail_url
    assert "image-to-video" in (entries[0].summary or "")
    assert entries[0].image_url == "https://x.ai/images/news/grok-imagine-1-5-og.webp"
    assert entries[0].author_names == ["xAI"]
    assert entries[0].published_at is not None


@pytest.mark.asyncio
async def test_arena_leaderboard_fetcher_reads_video_model_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Arena.ai Image-to-Video rows become reviewable benchmark news."""

    service = FrontierNewsService(cast(AsyncSession, object()), Settings(_env_file=None))
    source = FrontierNewsSource(
        key="arena_image_to_video",
        name="Arena.ai Image-to-Video 榜单",
        kind="arena_leaderboard",
        url="https://arena.ai/leaderboard/image-to-video",
        config={"max_items": 2, "keywords": ["grok", "image-to-video", "leaderboard"]},
        enabled=True,
        trust_level=85,
        fetch_interval_minutes=120,
    )

    async def fake_read_url(url: str) -> str:
        """Return deterministic Arena leaderboard HTML for this parser test."""

        assert url == source.url
        return """
            <h1>Image-to-Video Arena</h1>
            May 29, 2026
            <a href="https://docs.x.ai/developers/models/grok-imagine-video-1.5-preview"
               title="grok-imagine-video-1.5-preview-720p"></a>
            <span>xAI · Proprietary</span><span>1473±9</span><span>5,564</span>
            <a href="https://seed.bytedance.com/"
               title="dreamina-seedance-2.0-720p"></a>
            <span>Bytedance · Proprietary</span><span>1467±11</span>
        """

    monkeypatch.setattr(service, "_read_url", fake_read_url)

    entries = await service._fetch_arena_leaderboard_entries(source)

    assert len(entries) == 2
    assert entries[0].title == "grok-imagine-video-1.5-preview-720p"
    assert entries[0].url.startswith("https://docs.x.ai/developers/models/")
    assert "第 1 名" in (entries[0].summary or "")
    assert "1473±9" in (entries[0].summary or "")
    assert entries[0].author_names == ["Arena.ai", "xAI"]
    assert entries[1].title == "dreamina-seedance-2.0-720p"
    assert "第 2 名" in (entries[1].summary or "")
