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

    assert "# 微博热搜 2026-07-27" in markdown
    assert "不代表事实已经核实" in markdown
    assert "[一个好玩的热搜]" in markdown
    assert "热度 123456" in markdown


def test_write_snapshot_replaces_the_daily_file(tmp_path: Path) -> None:
    output_path = tmp_path / "2026-07-27.json"
    output_path.write_text('{"stale": true}\n', encoding="utf-8")
    snapshot = {"date": "2026-07-27", "count": 0, "topics": []}

    collector.write_snapshot(snapshot, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == snapshot
    assert not output_path.with_suffix(".json.tmp").exists()
