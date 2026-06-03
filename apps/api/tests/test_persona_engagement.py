from types import SimpleNamespace

from scripts.seed_persona_engagement import (
    TopicDraft,
    build_reply_body,
    plain_text,
    sample_viewers,
    seeded_rng,
    understand_topic,
    viewer_key_for_visitor,
)


# Verify full-post analysis does not stop at the first paragraph.
def test_understand_topic_keeps_later_paragraph_question() -> None:
    """Assert later-paragraph questions survive the local understanding step."""

    body = (
        "我点外卖经常备注一长串，比如少辣、不要葱、多放醋、米饭少一点。"
        "结果店里不是漏看，就是只做到其中一条。\n\n"
        "最近有点怀疑是我写得太复杂了。大家一般怎么写备注？"
        "是只写最重要的一条，还是分行写会更清楚？"
    )

    signals = understand_topic("外卖备注老是出错，是不是我写太复杂了", body)
    combined = " ".join(
        [
            signals.main_point,
            *signals.detail_points,
            *signals.question_points,
            *signals.action_points,
            signals.ending_point,
        ]
    )

    assert "写得太复杂" in combined
    assert "分行写会更清楚" in combined


# Verify persona replies anchor themselves to extracted full-post signals.
def test_build_reply_body_mentions_extracted_signal() -> None:
    """Assert generated replies quote at least one signal from the full post."""

    title = "外卖备注老是出错，是不是我写太复杂了"
    body = (
        "我点外卖经常备注一长串，比如少辣、不要葱、多放醋、米饭少一点。"
        "结果店里不是漏看，就是只做到其中一条。\n\n"
        "最近有点怀疑是我写得太复杂了。大家一般怎么写备注？"
        "是只写最重要的一条，还是分行写会更清楚？"
    )
    topic = SimpleNamespace(
        id="topic-1",
        title=title,
        board=SimpleNamespace(slug="qna"),
        tags=[],
        user_id="author-1",
    )
    first_post = SimpleNamespace(id="post-1", raw_md=body)
    signals = understand_topic(title, body)
    draft = TopicDraft(
        topic=topic,
        first_post=first_post,
        text=plain_text(f"{title}\n{body}"),
        understanding=signals,
    )
    user = SimpleNamespace(username="小K_再看看", id="persona-1")

    reply = build_reply_body(draft, user, seeded_rng("unit", "reply-body"))
    expected_signals = (
        signals.main_point,
        *signals.detail_points,
        *signals.question_points,
        signals.ending_point,
    )

    assert any(signal and signal in reply for signal in expected_signals)
    assert any(keyword in reply for keyword in ("少辣", "写得太复杂", "分行写会更清楚"))


# Verify upload links are stripped before reply snippets are generated.
def test_plain_text_removes_upload_urls() -> None:
    """Assert local reply context never carries attachment URLs into replies."""

    text = plain_text(
        "图片在 /api/v1/uploads/abc.png 以及 https://example.com/a.png 后面继续说重点"
    )

    assert "/api/v1/uploads" not in text
    assert "https://example.com" not in text
    assert "后面继续说重点" in text


# Verify topic view seeding uses stable dedupe keys for users and anonymous visitors.
def test_sample_viewers_adds_stable_user_and_anonymous_keys() -> None:
    """Assert planned viewers are deterministic and include anonymous overflow."""

    users = [
        SimpleNamespace(id="user-1", username="甲"),
        SimpleNamespace(id="user-2", username="乙"),
    ]

    viewers = sample_viewers(users, 4, "unit-seed", "topic-1")
    repeated = sample_viewers(users, 4, "unit-seed", "topic-1")

    assert [viewer.viewer_key for viewer in viewers] == [
        viewer.viewer_key for viewer in repeated
    ]
    assert sum(1 for viewer in viewers if viewer.authenticated) == 2
    assert sum(1 for viewer in viewers if not viewer.authenticated) == 2
    assert all(viewer.viewer_key.startswith(("user:", "anon:")) for viewer in viewers)
    assert viewer_key_for_visitor("unit-seed", "topic-1", 1) in {
        viewer.viewer_key for viewer in viewers
    }
