from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from publish_xiaoxiao_news import load_local_publisher_env, main as publish_main


# Read the first non-empty environment variable from the provided names.
# Key parameter `names` is the lookup order. Return value: trimmed env value or empty string. Side effect: none.
def first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


SPORTS_DEFAULT_ARGS = [
    "--author-username",
    "小小鸡仔",
    "--ensure-author",
    "--author-email",
    "xiaoxiao-jizai@pingxingxian.space",
    "--author-display-name",
    "小小鸡仔",
    "--author-avatar-file",
    "apps/web/public/avatars/xiaoxiao-jizai.png",
    "--board-slug",
    "sports",
    "--board-name",
    "体坛快讯",
    "--board-description",
    "聚合赛事新闻、球员动态、赛后热点与转会消息。",
    "--board-color",
    "#16A34A",
    "--tags",
    "乒乓球,体坛快讯",
    "--source-prefix",
    "manual-xiaoxiao-sports",
]

# Run the Xiaoxiao Chick sports publisher with caller-provided overrides last.
# Key parameter `argv` is optional CLI argv. Return value: publisher exit code. Side effect: preview/publish API calls.
def main(argv: list[str] | None = None) -> int:
    load_local_publisher_env()
    sports_public_credential_args = [
        "--account",
        first_env("PARALLELLINES_SPORTS_PUBLISH_ACCOUNT", "PARALLELLINES_PUBLISH_ACCOUNT"),
        "--password",
        first_env("PARALLELLINES_SPORTS_PUBLISH_PASSWORD", "PARALLELLINES_PUBLISH_PASSWORD"),
    ]
    return publish_main(
        [*SPORTS_DEFAULT_ARGS, *sports_public_credential_args, *(argv if argv is not None else sys.argv[1:])]
    )


if __name__ == "__main__":
    raise SystemExit(main())
