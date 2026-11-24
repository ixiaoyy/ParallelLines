from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import collect_weibo_hot_search as collector


def test_build_snapshot_filters_ads_duplicates_and_invalid_rows() -> None:
    payload = {
        "ok": 1,
        "data": {
            "hotgov": {"note": "置顶内容"},
            "realtime": [
                {
                    "realpos": 1,
                    "note": "第一条热搜",
                    "word_scheme": "#第一条热搜#",
                    "num": 900001,
                    "label_name": "热",
                    "topic_flag": 1,
                },
                {"realpos": 2, "note": "广告", "num": 800000, "is_ad": 1},
                {"realpos": 3, "note": "第一条热搜", "num": 700000},
                "invalid",
                {
                    "realpos": 5,
                    "word": "第二条热搜",
                    "num": "600000",
                    "flag_desc": "社会",
                },
            ],
        },
    }

    snapshot = collector.build_snapshot(
        payload,
        limit=10,
        include_ads=False,
        collected_at=datetime(2026, 7, 27, 8, 30, tzinfo=collector.SHANGHAI_TIMEZONE),
    )

    assert snapshot["date"] == "2026-07-27"
    assert snapshot["count"] == 2
    assert snapshot["pinned_item_excluded"] is True
    assert snapshot["topics"] == [
        {
            "rank": 1,
            "title": "第一条热搜",
            "heat": 900001,
            "label": "热",
            "category": "",
            "is_topic": True,
            "url": "https://s.weibo.com/weibo?q=%23%E7%AC%AC%E4%B8%80%E6%9D%A1%E7%83%AD%E6%90%9C%23",
        },
        {
            "rank": 5,
            "title": "第二条热搜",
            "heat": 600000,
            "label": "",
            "category": "社会",
            "is_topic": False,
            "url": "https://s.weibo.com/weibo?q=%E7%AC%AC%E4%BA%8C%E6%9D%A1%E7%83%AD%E6%90%9C",
        },
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"ok": 0, "data": {"realtime": []}},
        {"ok": 1},
        {"ok": 1, "data": {}},
    ],
)
def test_build_snapshot_rejects_invalid_payloads(payload: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError):
        collector.build_snapshot(payload, limit=20, include_ads=False)


def test_render_markdown_warns_that_trends_are_not_verified_facts() -> None:
    snapshot = collector.build_snapshot(
        {
            "ok": 1,
            "data": {
                "realtime": [
                    {"realpos": 1, "note": "一个好玩的热搜", "num": 123456, "label_name": "新"}
                ]
            },
        },
        limit=1,
        include_ads=False,
        collected_at=datetime(2026, 7, 27, 9, 0, tzinfo=collector.SHANGHAI_TIMEZONE),
    )

    markdown = collector.render_markdown(snapshot)

    assert markdown.startswith("# 微博热搜｜一个好玩的热搜\n\n1.")
    assert markdown.endswith("> 自动采集，仅反映热度，内容未核实。\n")
    assert "[一个好玩的热搜]" in markdown
    assert "热度 123456" in markdown
    assert "采集时间：2026-07-27T09:00:00+08:00" in markdown
    assert "来源：[微博热搜榜](https://s.weibo.com/top/summary)" in markdown
    assert markdown.index("[一个好玩的热搜]") < markdown.index("采集时间：")


def test_hot_search_title_uses_real_top_two_ranks_without_changing_input() -> None:
    """标题选来源名次前两项，不改原榜单数据或把日期拼入标题。"""

    topics = [
        {"rank": 3, "title": "第三个词条"},
        {"rank": 1, "title": "榜首词条"},
        {"rank": 2, "title": "第二个词条"},
    ]
    original = json.dumps(topics, ensure_ascii=False)
    assert collector.hot_search_title(topics) == "微博热搜｜榜首词条、第二个词条"
    assert json.dumps(topics, ensure_ascii=False) == original


@pytest.mark.parametrize("count", [1, 2])
def test_hot_search_title_shortens_only_real_words_to_a_bounded_length(count: int) -> None:
    """一个词条也可成题；超长词条以省略号截短，不添第三条或虚构描述。"""

    topics = [
        {"rank": index + 1, "title": ("甲" if index == 0 else "乙") * 100}
        for index in range(count)
    ]
    title = collector.hot_search_title(topics)
    assert len(title) <= collector.HOT_SEARCH_TITLE_LIMIT
    assert title.startswith("微博热搜｜甲") and title.endswith("…")
    assert title.count("、") == count - 1
    assert title.count("…") == count


def test_hot_search_title_keeps_single_topic_and_empty_snapshot_meaning() -> None:
    assert collector.hot_search_title([{"rank": 1, "title": "只有一个真实词条"}]) == (
        "微博热搜｜只有一个真实词条"
    )
    assert collector.hot_search_title([]) == "微博热搜"


def test_write_snapshot_replaces_the_daily_file(tmp_path: Path) -> None:
    output_path = tmp_path / "2026-07-27.json"
    output_path.write_text('{"stale": true}\n', encoding="utf-8")
    snapshot = {"date": "2026-07-27", "count": 0, "topics": []}

    collector.write_snapshot(snapshot, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == snapshot
    assert not output_path.with_suffix(".json.tmp").exists()
