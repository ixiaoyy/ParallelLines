from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "https://www.pingxingxian.space/api/v1"
DEFAULT_BOARD_SLUG = "frontier"
DEFAULT_TAGS = "动态,大模型,前沿资讯"
DEFAULT_TITLE = "Doubao-Seed-2.1-pro 发布，火山方舟同步上线 Seed 2.1 系列"
DEFAULT_BODY = """:::news-card
来源：火山引擎文档
[Doubao-Seed-2.1-pro 发布，火山方舟同步上线 Seed 2.1 系列](https://www.volcengine.com/docs/82379/2549861?lang=zh)

火山方舟文档显示，Doubao-Seed-2.1 系列已上线，提供 Pro、Turbo 及 Evolving 版本，面向 Coding、Agent 长链路任务与多模态理解场景。
:::

火山引擎火山方舟文档近日上线「最新模型：Seed 2.1」页面，确认 Doubao-Seed-2.1 系列已进入官方文档与模型接入体系。其中，Doubao-Seed-2.1-pro 面向高复杂度任务探索，Doubao-Seed-2.1-turbo 面向规模化生产场景；面向开发者 Coding、办公与生产力提效场景，火山方舟还提供周级更新的 Evolving 版本。

能力方面，Seed 2.1 重点覆盖 Coding 工程交付、Agent 长链路任务执行和多模态理解。文档显示，该系列支持图片、视频、文本理解，并支持深度思考能力；开发者可通过 `thinking` 参数控制是否开启思考，通过 `reasoning_effort` 调节思考长度。

规格方面，官方文档列出的上下文窗口、最大输入长度、最大思考内容长度和最大输出长度均为 256k。模型基本信息、价格与 API 支持情况，可在火山方舟控制台模型详情页查看。

来源：

- [火山方舟文档：最新模型 Seed 2.1](https://www.volcengine.com/docs/82379/2549861?lang=zh)
- [火山方舟控制台](https://console.volcengine.com/ark)
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for API-based frontier news publishing.

    Key parameter `argv` allows callers or tests to pass explicit arguments.
    Return value is the parsed namespace. Side effects: none.
    """

    load_local_publisher_env()
    parser = argparse.ArgumentParser(
        description="Publish one frontier news topic through the production HTTP API."
    )
    parser.add_argument("--api-base-url", default=os.getenv("PARALLELLINES_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--account", default=os.getenv("PARALLELLINES_PUBLISH_ACCOUNT"))
    parser.add_argument("--password", default=os.getenv("PARALLELLINES_PUBLISH_PASSWORD"))
    parser.add_argument("--board-slug", default=os.getenv("PARALLELLINES_PUBLISH_BOARD", DEFAULT_BOARD_SLUG))
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--body", default=None, help="Markdown body. Defaults to the built-in Seed 2.1 draft.")
    parser.add_argument("--body-file", help="UTF-8 Markdown file to publish as the body.")
    parser.add_argument("--tags", default=DEFAULT_TAGS, help="Comma-separated topic tags.")
    parser.add_argument("--force", action="store_true", help="Publish even if a recent topic has the same title.")
    parser.add_argument("--dry-run", action="store_true", help="Validate input and print the request plan only.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the API publishing workflow and print a JSON result.

    Key parameter `argv` is forwarded to `parse_args`. Return value is none.
    Side effect: may create one topic on the configured API unless `--dry-run` is set.
    """

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    result = publish_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def publish_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Publish or preview a topic using parsed CLI arguments.

    Key parameter `args` contains API location, credentials, and topic content.
    Return value summarizes the action. Side effect: logs in and posts to the
    remote API unless `args.dry_run` is true.
    """

    title = args.title.strip()
    body = read_body(args)
    tags = parse_tags(args.tags)
    plan = {
        "api_base_url": normalize_api_base_url(args.api_base_url),
        "board_slug": args.board_slug,
        "title": title,
        "tags": tags,
        "body_chars": len(body),
        "account_configured": bool(args.account),
        "password_configured": bool(args.password),
    }
    if args.dry_run:
        return {"dry_run": True, "would_publish": plan}
    require_credentials(args)

    api = ApiClient(plan["api_base_url"])
    login_data = api.login(args.account, args.password)
    token = login_data["access_token"]
    if not args.force:
        existing = api.find_recent_topic(args.board_slug, title)
        if existing:
            return {
                "created": False,
                "reason": "existing_recent_topic",
                "topic": summarize_topic(existing),
            }
    topic = api.create_topic(
        board_slug=args.board_slug,
        token=token,
        title=title,
        body=body,
        tags=tags,
    )
    return {"created": True, "topic": summarize_topic(topic)}


def require_credentials(args: argparse.Namespace) -> None:
    """Fail fast when API login credentials are missing.

    Key parameter `args` carries account/password values. Return value is none.
    Side effect: exits the process with a clear error for scheduler logs.
    """

    missing = []
    if not args.account:
        missing.append("PARALLELLINES_PUBLISH_ACCOUNT or --account")
    if not args.password:
        missing.append("PARALLELLINES_PUBLISH_PASSWORD or --password")
    if missing:
        raise SystemExit("Missing publisher credential: " + ", ".join(missing))


def load_local_publisher_env() -> None:
    """Load ignored local publisher credentials when present.

    Key parameters: none. Return value: none. Side effect: fills missing
    `PARALLELLINES_PUBLISH_*` environment variables from `.tmp/frontier-publisher.env`.
    """

    env_path = Path(__file__).resolve().parents[3] / ".tmp" / "frontier-publisher.env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def read_body(args: argparse.Namespace) -> str:
    """Return Markdown body text from CLI args, a file, or the default draft.

    Key parameter `args` contains `body` and `body_file`. Return value is stripped
    Markdown text. Side effect: reads `body_file` when provided.
    """

    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8").strip()
    if args.body:
        return args.body.strip()
    return DEFAULT_BODY.strip()


def parse_tags(tags_arg: str) -> list[str]:
    """Parse comma-separated tags and remove duplicates while preserving order.

    Key parameter `tags_arg` is a comma-separated label list. Return value is
    capped to the topic API limit. Side effects: none.
    """

    tags: list[str] = []
    for raw_tag in tags_arg.split(","):
        tag = raw_tag.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:8]


def normalize_api_base_url(api_base_url: str) -> str:
    """Return a stable API base URL without trailing slash.

    Key parameter `api_base_url` is a user or environment supplied URL. Return
    value is normalized for path joining. Side effects: none.
    """

    return api_base_url.rstrip("/")


def summarize_topic(topic: dict[str, Any]) -> dict[str, Any]:
    """Extract stable topic fields for script output.

    Key parameter `topic` is an API topic object. Return value is safe to print
    in logs and intentionally excludes credentials. Side effects: none.
    """

    return {
        "id": topic.get("id"),
        "title": topic.get("title"),
        "share_url": topic.get("share_url"),
        "author_name": topic.get("author_name"),
        "created_at": topic.get("created_at"),
    }


class ApiClient:
    """Small JSON client for the ParallelLines public API."""

    def __init__(self, api_base_url: str) -> None:
        """Store a normalized API base URL.

        Key parameter `api_base_url` is the `/api/v1` root. Return value is none.
        Side effects: none.
        """

        self.api_base_url = normalize_api_base_url(api_base_url)

    def login(self, account: str, password: str) -> dict[str, Any]:
        """Log in with a regular account and return token data.

        Key parameters are user-facing credentials. Return value is the API data
        object. Side effect: creates a normal server session.
        """

        data = self.request_json(
            "POST",
            "/auth/login",
            {"account": account, "password": password},
            token=None,
        )
        if data.get("two_factor_required"):
            raise SystemExit("Publisher account has 2FA enabled; this script does not handle 2FA.")
        if not data.get("access_token"):
            raise SystemExit("Login succeeded without an access token.")
        return data

    def find_recent_topic(self, board_slug: str, title: str) -> dict[str, Any] | None:
        """Return a recent same-title topic from one board when present.

        Key parameters identify the board and exact title. Return value is an API
        topic object or `None`. Side effect: reads the public topic feed.
        """

        query = urlencode({"sort": "latest", "limit": 20})
        data = self.request_json("GET", f"/boards/{board_slug}/topics?{query}", payload=None, token=None)
        for topic in data:
            if topic.get("title") == title:
                return topic
        return None

    def create_topic(
        self,
        *,
        board_slug: str,
        token: str,
        title: str,
        body: str,
        tags: list[str],
    ) -> dict[str, Any]:
        """Create one public topic in the target board.

        Key parameters describe the board, auth token, and topic payload. Return
        value is the created topic object. Side effect: writes to the remote API.
        """

        return self.request_json(
            "POST",
            f"/boards/{board_slug}/topics",
            {
                "title": title,
                "raw_md": body,
                "tags": tags,
                "pinned": False,
                "featured": False,
            },
            token=token,
        )

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        token: str | None,
    ) -> Any:
        """Send one JSON request and return the API envelope data.

        Key parameters are HTTP method, path, optional payload, and optional
        bearer token. Return value is `response.data`. Side effect: performs one
        network request and raises a clear error for non-2xx responses.
        """

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ParallelLinesFrontierPublisher/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            self.api_base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"API request failed: {exc.code} {error_body}") from exc
        except URLError as exc:
            raise SystemExit(f"API request failed: {exc}") from exc
        if "error" in response_data:
            raise SystemExit(f"API error: {json.dumps(response_data['error'], ensure_ascii=False)}")
        return response_data.get("data")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

