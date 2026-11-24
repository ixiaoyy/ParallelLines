from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

WEIBO_HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"
WEIBO_SEARCH_URL = "https://s.weibo.com/weibo?q="
WEIBO_REFERER = "https://weibo.com/hot/search"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "var" / "weibo-hot-search"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
HOT_SEARCH_TITLE_LIMIT = 64
HOT_SEARCH_AUTOMATION_MARKER = "> 自动采集，仅反映热度，内容未核实。"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for one Weibo hot-search snapshot."""

    parser = argparse.ArgumentParser(
        description="Collect the current Weibo hot-search list as a daily JSON snapshot."
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of topics to keep (1-50).")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Console output format. Saved snapshots are always JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Snapshot path. Defaults to apps/api/var/weibo-hot-search/YYYY-MM-DD.json.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print the snapshot without writing the daily JSON file.",
    )
    parser.add_argument(
        "--include-ads",
        action="store_true",
        help="Keep entries explicitly marked as advertisements.",
    )
    return parser.parse_args(argv)


def fetch_hot_search_payload(
    *,
    timeout: float,
    source_url: str = WEIBO_HOT_SEARCH_URL,
) -> Mapping[str, Any]:
    """Fetch and decode one Weibo hot-search response.

    Key parameters are the request timeout and overridable source URL. Return
    value is the decoded response mapping. Side effect: performs one HTTP GET.
    """

    request = Request(
        source_url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": WEIBO_REFERER,
            "User-Agent": USER_AGENT,
        },
    )
    if not 0 < timeout <= 30:
        raise ValueError("timeout must be greater than zero and at most 30 seconds")
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            # 定时采集限制响应体和总耗时，避免慢响应或异常大榜单占满常驻任务。
            chunks: list[bytes] = []
            size = 0
            while True:
                if time.monotonic() - started > timeout:
                    raise RuntimeError("Weibo hot-search response exceeded the total time limit")
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Weibo hot-search response exceeded the size limit")
                chunks.append(chunk)
            raw_body = b"".join(chunks).decode(encoding, errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Weibo hot-search request returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Weibo hot-search request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Weibo hot-search response was not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("Weibo hot-search response must be a JSON object")
    return payload


def build_snapshot(
    payload: Mapping[str, Any],
    *,
    limit: int,
    include_ads: bool,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    """Normalize a Weibo response into a stable daily snapshot.

    Key parameters select the maximum topic count, advertisement policy, and
    optional collection time. Return value is JSON-safe. Side effects: none.
    """

    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if payload.get("ok") != 1:
        raise RuntimeError("Weibo hot-search response reported an unsuccessful status")

    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise RuntimeError("Weibo hot-search response is missing the data object")
    realtime = data.get("realtime")
    if not isinstance(realtime, list):
        raise RuntimeError("Weibo hot-search response is missing the realtime list")

    topics: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for position, raw_item in enumerate(realtime, start=1):
        if not isinstance(raw_item, Mapping):
            continue
        if _is_advertisement(raw_item) and not include_ads:
            continue

        title = _topic_title(raw_item)
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        search_term = _text(raw_item.get("word_scheme")) or title
        topics.append(
            {
                "rank": _positive_int(raw_item.get("realpos"))
                or _positive_int(raw_item.get("rank"))
                or position,
                "title": title,
                "heat": _non_negative_int(raw_item.get("num")),
                "label": _text(raw_item.get("label_name")) or _text(raw_item.get("icon_desc")),
                "category": _text(raw_item.get("flag_desc")),
                "is_topic": bool(raw_item.get("topic_flag")),
                "url": WEIBO_SEARCH_URL + quote(search_term, safe=""),
            }
        )
        if len(topics) >= limit:
            break

    timestamp = (collected_at or datetime.now(SHANGHAI_TIMEZONE)).astimezone(SHANGHAI_TIMEZONE)
    return {
        "source": "weibo_hot_search",
        "source_url": WEIBO_HOT_SEARCH_URL,
        "list_url": "https://s.weibo.com/top/summary",
        "date": timestamp.date().isoformat(),
        "collected_at": timestamp.isoformat(timespec="seconds"),
        "count": len(topics),
        "ads_included": include_ads,
        "pinned_item_excluded": bool(data.get("hotgov") or data.get("hotgovs")),
        "topics": topics,
    }


def hot_search_title(topics: Sequence[Mapping[str, object]]) -> str:
    """用真实榜单前两项生成短标题；空榜返回栏目名，不改榜单或去重数据。"""

    # 以来源名次选标题；无名次的旧快照项保持原相对顺序，排在有效名次后。
    ranked = sorted(topics, key=lambda topic: _positive_int(topic.get("rank")) or sys.maxsize)
    titles = [" ".join(_text(topic.get("title")).split()) for topic in ranked]
    titles = [title for title in titles if title][:2]
    if not titles:
        return "微博热搜"
    prefix, separator = "微博热搜｜", "、"
    limit = (HOT_SEARCH_TITLE_LIMIT - len(prefix) - len(titles) + 1) // len(titles)
    # 只截短已有词条，不把词条扩写成已核实的事件经过。
    titles = [title if len(title) <= limit else title[: limit - 1] + "…" for title in titles]
    return prefix + separator.join(titles)


def render_markdown(snapshot: Mapping[str, Any]) -> str:
    """Render a compact discovery digest from a normalized snapshot."""

    topics = snapshot.get("topics")
    rendered = (
        [topic for topic in topics if isinstance(topic, Mapping)]
        if isinstance(topics, list)
        else []
    )
    lines = [f"# {hot_search_title(rendered)}", ""]
    for topic in rendered:
        label = f" · {topic['label']}" if topic.get("label") else ""
        heat = f" · 热度 {topic['heat']}" if topic.get("heat") is not None else ""
        lines.append(f"{topic['rank']}. [{topic['title']}]({topic['url']}){label}{heat}")
    # 元信息与短说明放在榜单后，列表摘要优先显示真实词条。
    lines.extend(
        [
            "",
            f"采集时间：{snapshot['collected_at']}",
            "",
            "来源：[微博热搜榜](https://s.weibo.com/top/summary)",
            "",
            HOT_SEARCH_AUTOMATION_MARKER,
        ]
    )
    return "\n".join(lines) + "\n"


def write_snapshot(snapshot: Mapping[str, Any], output_path: Path) -> None:
    """Write a JSON snapshot atomically.

    Key parameters are the normalized snapshot and destination. Return value is
    none. Side effect: creates parent directories and replaces the destination.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)


def default_output_path(snapshot_date: str) -> Path:
    """Return the ignored daily archive path for one snapshot date."""

    return DEFAULT_OUTPUT_DIR / f"{snapshot_date}.json"


def main(argv: Sequence[str] | None = None) -> int:
    """Collect, optionally persist, and print one hot-search snapshot."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        snapshot = build_snapshot(
            fetch_hot_search_payload(timeout=args.timeout),
            limit=args.limit,
            include_ads=args.include_ads,
        )
        output_path = args.output or default_output_path(snapshot["date"])
        if not args.no_save:
            write_snapshot(snapshot, output_path)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"collect_weibo_hot_search: {exc}", file=sys.stderr)
        return 1

    if args.format == "markdown":
        print(render_markdown(snapshot), end="")
    else:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


def _topic_title(item: Mapping[str, Any]) -> str:
    """Return the preferred visible title for one raw hot-search item."""

    return _text(item.get("note")) or _text(item.get("word"))


def _is_advertisement(item: Mapping[str, Any]) -> bool:
    """Return whether Weibo explicitly marks a raw item as an advertisement."""

    value = item.get("is_ad")
    return value is True or value == 1 or value == "1"


def _text(value: object) -> str:
    """Normalize an optional scalar value to stripped text."""

    return str(value).strip() if value is not None else ""


def _positive_int(value: object) -> int | None:
    """Return a positive integer or none for an invalid value."""

    parsed = _integer(value)
    return parsed if parsed is not None and parsed > 0 else None


def _non_negative_int(value: object) -> int | None:
    """Return a non-negative integer or none for an invalid value."""

    parsed = _integer(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _integer(value: object) -> int | None:
    """Return an integer for supported JSON scalar values."""

    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
