from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import jwt


# Resolve the ParallelLines repository root from this skill script location.
# Key parameters: none. Return value: repository root path. Side effect: none.
def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


# Read a simple KEY=VALUE .env file without logging secrets.
# Key parameter `path` is the env file path. Return value: parsed key/value map. Side effect: file read.
def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


# Send a JSON API request and parse the JSON response.
# Key parameters are HTTP method, URL, optional bearer token, and optional JSON payload. Side effect: network I/O.
def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured project API.
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {error_body[:800]}") from exc
    return json.loads(response_body or "{}")


# Look up a public user profile and return its id after optional role validation.
# Key parameters are public base URL, username, and expected role. Side effect: network I/O.
def public_user_id(base_url: str, username: str, *, expected_role: str | None = None) -> str:
    profile = request_json("GET", f"{base_url}/api/v1/users/{quote(username)}")
    data = dict(profile.get("data") or {})
    if expected_role and data.get("role") != expected_role:
        raise RuntimeError(f"{username} role is {data.get('role')!r}, expected {expected_role!r}")
    user_id = str(data.get("id") or "")
    if not user_id:
        raise RuntimeError(f"Could not resolve user id for {username}")
    return user_id


# Build a short-lived admin access token from the local API JWT settings.
# Key parameters are admin user id and env values. Return value: JWT string. Side effect: none.
def make_admin_token(admin_id: str, env_values: dict[str, str]) -> str:
    secret = env_values.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is missing from apps/api/.env")
    algorithm = env_values.get("JWT_ALGORITHM") or "HS256"
    now = datetime.now(UTC)
    payload = {
        "sub": admin_id,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


# Normalize comma-separated tags while preserving user-specified order.
# Key parameter `raw_tags` is the CLI tag string. Return value: unique tag list. Side effect: none.
def normalize_tags(raw_tags: str) -> list[str]:
    tags: list[str] = []
    for item in raw_tags.split(","):
        tag = item.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


# Create a conservative ASCII slug fallback when the caller does not provide one.
# Key parameter `title` is the post title. Return value: ASCII slug. Side effect: none.
def fallback_slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if slug:
        return slug[:80]
    return "manual-news-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


# Build the migration import payload accepted by ParallelLines admin APIs.
# Key parameters are CLI args and Markdown body. Return value: request payload. Side effect: none.
def build_payload(args: argparse.Namespace, body: str, *, source: str) -> dict[str, Any]:
    slug = args.slug.strip() if args.slug else fallback_slug(args.title)
    return {
        "source": source,
        "users": [],
        "boards": [
            {
                "slug": args.board_slug,
                "name": args.board_name,
                "description": args.board_description,
                "color": args.board_color,
            }
        ],
        "topics": [
            {
                "external_id": args.external_id or f"manual-{slug}",
                "board_slug": args.board_slug,
                "author_username": args.author_username,
                "title": args.title.strip(),
                "slug": slug,
                "tags": normalize_tags(args.tags),
                "raw_md": body.strip(),
            }
        ],
        "posts": [],
    }


# Print a compact import result without exposing credentials.
# Key parameters are a label and API response data. Return value: none. Side effect: console output.
def print_import_result(label: str, response: dict[str, Any]) -> None:
    data = dict(response.get("data") or {})
    print(
        f"{label}: dry_run={data.get('dry_run')} created={data.get('created')} "
        f"updated={data.get('updated')} skipped={data.get('skipped')} errors={data.get('errors')}"
    )
    for row in data.get("rows") or []:
        print(f"- {row.get('resource')} {row.get('key')}: {row.get('action')} ({row.get('message')})")


# Search the public API for the newly published topic and print matching URLs.
# Key parameters are base URL and title. Return value: none. Side effect: network I/O and console output.
def verify_public_topic(base_url: str, title: str) -> None:
    response = request_json(
        "GET",
        f"{base_url}/api/v1/topics?q={quote(title)}&limit=5",
        timeout=20,
    )
    matches = [item for item in response.get("data") or [] if item.get("title") == title]
    if not matches:
        print("Verification: no exact public title match found yet.")
        return
    for item in matches:
        print(
            "Verification: "
            f"{item.get('id')} {item.get('author_name')} "
            f"{base_url}{item.get('share_url')}"
        )


# Parse CLI arguments for one preview or publish operation.
# Key parameter `argv` is optional CLI argv. Return value: parsed args. Side effect: may print help.
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or publish a ParallelLines frontier news post as Xiaoxiao.",
    )
    parser.add_argument("--title", required=True, help="Post title.")
    parser.add_argument("--body-file", required=True, help="Markdown body file path, or '-' for stdin.")
    parser.add_argument("--slug", default="", help="Short ASCII topic slug.")
    parser.add_argument("--tags", default="动态,大模型,前沿资讯", help="Comma-separated tags.")
    parser.add_argument("--run", action="store_true", help="Actually publish after a successful preview.")
    parser.add_argument("--base-url", default="https://www.pingxingxian.space", help="Public site URL.")
    parser.add_argument("--env-file", default=str(project_root() / "apps/api/.env"), help="API .env path.")
    parser.add_argument("--admin-username", default="多动脑子z", help="Admin username for signing token.")
    parser.add_argument("--author-username", default="小小资讯", help="Topic author username.")
    parser.add_argument("--board-slug", default="frontier", help="Target board slug.")
    parser.add_argument("--board-name", default="热点资讯", help="Target board display name.")
    parser.add_argument(
        "--board-description",
        default="自动汇集 AI 科技与社会热点，经人工审核后发布。",
        help="Board description used by migration payload when the board already exists.",
    )
    parser.add_argument("--board-color", default="#6366F1", help="Board color used by migration payload.")
    parser.add_argument("--external-id", default="", help="Optional stable migration external id.")
    return parser.parse_args(argv)


# Execute preview and, when requested, publish via the migration import API.
# Key parameter `argv` is optional CLI argv. Return value: process exit code. Side effect: API writes only with --run.
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    body_path = Path(args.body_file)
    body = sys.stdin.read() if args.body_file == "-" else body_path.read_text(encoding="utf-8")
    if not body.strip():
        raise RuntimeError("Body is empty")

    env_values = load_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/")
    admin_id = public_user_id(base_url, args.admin_username, expected_role="admin")
    token = make_admin_token(admin_id, env_values)

    preview_payload = build_payload(args, body, source="manual-xiaoxiao-news-preview")
    preview = request_json(
        "POST",
        f"{base_url}/api/v1/admin/migrations/import/preview",
        token=token,
        payload=preview_payload,
    )
    print_import_result("Preview", preview)
    preview_data = dict(preview.get("data") or {})
    if int(preview_data.get("errors") or 0) > 0:
        raise RuntimeError("Preview returned errors; aborting")
    if not args.run:
        print("Preview only. Re-run with --run to publish.")
        return 0
    if not any(row.get("resource") == "topic" and row.get("action") == "created" for row in preview_data.get("rows") or []):
        raise RuntimeError("Preview did not create a topic; refusing to run")

    run_payload = build_payload(args, body, source="manual-xiaoxiao-news")
    result = request_json(
        "POST",
        f"{base_url}/api/v1/admin/migrations/import/run",
        token=token,
        payload=run_payload,
    )
    print_import_result("Run", result)
    verify_public_topic(base_url, args.title.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
