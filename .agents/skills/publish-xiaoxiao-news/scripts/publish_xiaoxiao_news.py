from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import jwt

API_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


# Load ignored local publisher credentials when present so automations can reuse
# one local secret file without printing it.
def load_local_publisher_env() -> None:
    env_path = project_root() / ".tmp" / "frontier-publisher.env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


# Return the first non-empty environment variable from a priority list.
# Key parameter `names` is the lookup order. Return value: trimmed string. Side effect: none.
def first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


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
    headers = {"Accept": "application/json", "User-Agent": API_USER_AGENT}
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


# Upload one multipart file and parse the JSON API response.
# Key parameters are URL, bearer token, form field name, and file path. Side effect: network I/O.
def request_multipart_file_json(
    url: str,
    *,
    token: str,
    field_name: str,
    file_path: Path,
    timeout: int = 60,
) -> dict[str, Any]:
    boundary = f"----ParallelLines{uuid4().hex}"
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_content = file_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {media_type}\r\n\r\n".encode("ascii"),
            file_content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "User-Agent": API_USER_AGENT,
    }
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured project API.
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {error_body[:800]}") from exc
    return json.loads(response_body or "{}")


# Look up a public user profile and return its id after optional role validation.
# Key parameters are public base URL and username. Return value: profile data. Side effect: network I/O.
def public_user_profile(base_url: str, username: str) -> dict[str, Any]:
    profile = request_json("GET", f"{base_url}/api/v1/users/{quote(username)}")
    return dict(profile.get("data") or {})


# Read the currently authenticated public profile for one access token.
# Key parameters are public base URL and bearer token. Return value: profile data. Side effect: network I/O.
def authenticated_profile(base_url: str, token: str) -> dict[str, Any]:
    response = request_json("GET", f"{base_url}/api/v1/auth/me", token=token)
    return dict(response.get("data") or {})


# Look up a public user profile and return its id after optional role validation.
# Key parameters are public base URL, username, and expected role. Side effect: network I/O.
def public_user_id(base_url: str, username: str, *, expected_role: str | None = None) -> str:
    data = public_user_profile(base_url, username)
    if expected_role and data.get("role") != expected_role:
        raise RuntimeError(f"{username} role is {data.get('role')!r}, expected {expected_role!r}")
    user_id = str(data.get("id") or "")
    if not user_id:
        raise RuntimeError(f"Could not resolve user id for {username}")
    return user_id


# Build a short-lived access token from the local API JWT settings.
# Key parameters are user id and env values. Return value: JWT string. Side effect: none.
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


# Read an admin access token from CLI text, a file, a login request, or the legacy signer.
# Key parameters are base URL, CLI args, and env values. Return value: admin JWT. Side effect: optional network login.
def resolve_admin_token(base_url: str, args: argparse.Namespace, env_values: dict[str, str]) -> str:
    token = args.admin_token.strip()
    if token:
        return token
    if args.admin_token_file:
        token_path = Path(args.admin_token_file)
        if not token_path.is_absolute():
            token_path = project_root() / token_path
        token = token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError(f"Admin token file is empty: {token_path}")
        return token
    if args.admin_account and args.admin_password:
        return login_admin_token(base_url, args.admin_account, args.admin_password)
    admin_id = public_user_id(base_url, args.admin_username, expected_role="admin")
    return make_admin_token(admin_id, env_values)


# Log in through the public auth API and return its session-backed access token.
# Key parameters are base URL, admin account, and password. Return value: access token. Side effect: creates a server session.
def login_admin_token(base_url: str, account: str, password: str) -> str:
    response = request_json(
        "POST",
        f"{base_url}/api/v1/auth/login",
        payload={"account": account, "password": password},
    )
    data = dict(response.get("data") or {})
    if data.get("two_factor_required"):
        raise RuntimeError("Admin account has 2FA enabled; provide --admin-token-file instead")
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("Admin login succeeded without an access token")
    return token


# Log in through the public auth API for a normal publisher account.
# Key parameters are base URL, account, and password. Return value: access token. Side effect: creates a server session.
def login_publisher_token(base_url: str, account: str, password: str) -> str:
    response = request_json(
        "POST",
        f"{base_url}/api/v1/auth/login",
        payload={"account": account, "password": password},
    )
    data = dict(response.get("data") or {})
    if data.get("two_factor_required"):
        raise RuntimeError("Publisher account has 2FA enabled; provide a non-2FA publishing account")
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("Publisher login succeeded without an access token")
    return token


# Confirm the chosen token belongs to an active admin before invoking admin imports.
# Key parameters are base URL and token. Return value: none. Side effect: network validation request.
def validate_admin_token(base_url: str, token: str) -> None:
    try:
        response = request_json("GET", f"{base_url}/api/v1/auth/me", token=token)
    except RuntimeError as exc:
        raise RuntimeError(
            "Admin token was rejected by the production API. "
            "Use --admin-account/--admin-password or --admin-token-file with a session-backed admin token."
        ) from exc
    data = dict(response.get("data") or {})
    if data.get("role") != "admin":
        raise RuntimeError(f"Authenticated token role is {data.get('role')!r}, expected 'admin'")


# Confirm the chosen token belongs to the expected publishing account.
# Key parameters are base URL, token, and expected username. Return value: authenticated profile. Side effect: network validation request.
def validate_public_author_token(base_url: str, token: str, expected_username: str) -> dict[str, Any]:
    data = authenticated_profile(base_url, token)
    username = str(data.get("username") or "")
    if username != expected_username:
        raise RuntimeError(
            f"Publisher token belongs to {username or '<unknown>'!r}, expected author {expected_username!r}. "
            "Use the persona account credentials for public publishing."
        )
    if data.get("status") != "active":
        raise RuntimeError(f"Publisher account {expected_username!r} is not active")
    return data


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


# Build optional user records for persona accounts that may not exist yet.
# Key parameter `args` is the parsed CLI namespace. Return value: migration user rows. Side effect: none.
def author_user_records(args: argparse.Namespace) -> list[dict[str, str]]:
    if not args.ensure_author:
        return []
    email = args.author_email.strip()
    if not email:
        raise RuntimeError("--author-email is required when --ensure-author is set")
    display_name = args.author_display_name.strip() or args.author_username.strip()
    return [
        {
            "username": args.author_username.strip(),
            "email": email,
            "display_name": display_name,
        }
    ]


# Resolve and validate the optional author avatar file.
# Key parameter `args` is the parsed CLI namespace. Return value: file path or None. Side effect: none.
def author_avatar_path(args: argparse.Namespace) -> Path | None:
    if not args.author_avatar_file:
        return None
    avatar_path = Path(args.author_avatar_file)
    if not avatar_path.is_absolute():
        avatar_path = project_root() / avatar_path
    if not avatar_path.is_file():
        raise RuntimeError(f"Author avatar file does not exist: {avatar_path}")
    return avatar_path


# Build the migration import payload accepted by ParallelLines admin APIs.
# Key parameters are CLI args and Markdown body. Return value: request payload. Side effect: none.
def build_payload(args: argparse.Namespace, body: str, *, source: str) -> dict[str, Any]:
    slug = args.slug.strip() if args.slug else fallback_slug(args.title)
    return {
        "source": source,
        "users": author_user_records(args),
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


# Print a compact preview or run result for the public topic API using the same
# shape as migration preview logs.
# Key parameters are a label and synthetic response payload. Return value: none. Side effect: console output.
def print_public_result(label: str, response: dict[str, Any]) -> None:
    print_import_result(label, {"data": response})


# Return recent board topics for duplicate detection before public publishing.
# Key parameters are base URL and board slug. Return value: topic list. Side effect: network I/O.
def recent_board_topics(base_url: str, board_slug: str, *, limit: int = 20) -> list[dict[str, Any]]:
    response = request_json(
        "GET",
        f"{base_url}/api/v1/boards/{quote(board_slug)}/topics?sort=latest&limit={limit}",
        timeout=20,
    )
    return [dict(item) for item in response.get("data") or []]


# Find an exact-title recent topic in the target board.
# Key parameters are base URL, board slug, and title. Return value: topic object or None. Side effect: network I/O.
def find_recent_same_title_topic(base_url: str, board_slug: str, title: str) -> dict[str, Any] | None:
    for topic in recent_board_topics(base_url, board_slug):
        if str(topic.get("title") or "") == title:
            return topic
    return None


# Build a synthetic preview result for public topic publishing without writing.
# Key parameters are CLI args, body, and authenticated author profile. Return value: preview payload. Side effect: optional duplicate read.
def build_public_preview(
    base_url: str,
    args: argparse.Namespace,
    body: str,
    author_profile: dict[str, Any],
) -> dict[str, Any]:
    duplicate = None if args.force else find_recent_same_title_topic(base_url, args.board_slug, args.title.strip())
    if duplicate:
        return {
            "dry_run": True,
            "created": 0,
            "updated": 0,
            "skipped": 1,
            "errors": 0,
            "rows": [
                {
                    "resource": "topic",
                    "key": args.title.strip(),
                    "action": "skipped",
                    "message": f"Recent same-title topic exists: {duplicate.get('share_url')}",
                }
            ],
        }
    return {
        "dry_run": True,
        "created": 1,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "rows": [
            {
                "resource": "topic",
                "key": args.title.strip(),
                "action": "created",
                "message": f"Public API ready as {author_profile.get('username')}",
            }
        ],
    }


# Create one topic through the public board topic API.
# Key parameters are base URL, auth token, and CLI args/body. Return value: created topic object. Side effect: remote write.
def create_public_topic(
    base_url: str,
    token: str,
    args: argparse.Namespace,
    body: str,
) -> dict[str, Any]:
    response = request_json(
        "POST",
        f"{base_url}/api/v1/boards/{quote(args.board_slug)}/topics",
        token=token,
        payload={
            "title": args.title.strip(),
            "raw_md": body.strip(),
            "tags": normalize_tags(args.tags),
            "pinned": False,
            "featured": False,
        },
    )
    return dict(response.get("data") or {})


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


# Upload an optional author avatar after the topic has been published.
# Key parameters are base URL, CLI args, and env values. Return value: none. Side effect: API upload.
def upload_author_avatar_if_requested(
    base_url: str,
    args: argparse.Namespace,
    env_values: dict[str, str],
) -> None:
    avatar_path = author_avatar_path(args)
    if avatar_path is None:
        return
    profile = public_user_profile(base_url, args.author_username)
    existing_avatar_url = str(profile.get("avatar_url") or "")
    if existing_avatar_url and not args.force_author_avatar:
        print(f"Avatar: {profile.get('username')} {existing_avatar_url} (skipped)")
        return
    author_id = str(profile.get("id") or "")
    if not author_id:
        raise RuntimeError(f"Could not resolve user id for {args.author_username}")
    author_token = make_admin_token(author_id, env_values)
    try:
        response = request_multipart_file_json(
            f"{base_url}/api/v1/uploads/avatar",
            token=author_token,
            field_name="file",
            file_path=avatar_path,
        )
        data = dict(response.get("data") or {})
        print(f"Avatar: {data.get('username')} {data.get('avatar_url')}")
    except RuntimeError:
        refreshed = public_user_profile(base_url, args.author_username)
        refreshed_avatar_url = str(refreshed.get("avatar_url") or "")
        if refreshed_avatar_url and refreshed_avatar_url != existing_avatar_url:
            print(f"Avatar: {refreshed.get('username')} {refreshed_avatar_url} (verified after response error)")
            return
        raise


# Upload an optional author avatar using the same public author session token.
# Key parameters are base URL, CLI args, and author token. Return value: none. Side effect: API upload.
def upload_author_avatar_with_public_token(
    base_url: str,
    args: argparse.Namespace,
    token: str,
) -> None:
    avatar_path = author_avatar_path(args)
    if avatar_path is None:
        return
    profile = public_user_profile(base_url, args.author_username)
    existing_avatar_url = str(profile.get("avatar_url") or "")
    if existing_avatar_url and not args.force_author_avatar:
        print(f"Avatar: {profile.get('username')} {existing_avatar_url} (skipped)")
        return
    response = request_multipart_file_json(
        f"{base_url}/api/v1/uploads/avatar",
        token=token,
        field_name="file",
        file_path=avatar_path,
    )
    data = dict(response.get("data") or {})
    print(f"Avatar: {data.get('username')} {data.get('avatar_url')}")


# Parse CLI arguments for one preview or publish operation.
# Key parameter `argv` is optional CLI argv. Return value: parsed args. Side effect: may print help.
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    load_local_publisher_env()
    parser = argparse.ArgumentParser(
        description="Preview or publish a ParallelLines topic through the admin migration API.",
    )
    parser.add_argument("--title", required=True, help="Post title.")
    parser.add_argument("--body-file", required=True, help="Markdown body file path, or '-' for stdin.")
    parser.add_argument("--slug", default="", help="Short ASCII topic slug.")
    parser.add_argument("--tags", default="动态,大模型,前沿资讯", help="Comma-separated tags.")
    parser.add_argument("--run", action="store_true", help="Actually publish after a successful preview.")
    parser.add_argument(
        "--publish-mode",
        choices=("auto", "admin", "public"),
        default="auto",
        help="Publish via admin migration import or normal public create-topic API.",
    )
    parser.add_argument("--base-url", default="https://www.pingxingxian.space", help="Public site URL.")
    parser.add_argument("--env-file", default=str(project_root() / "apps/api/.env"), help="API .env path.")
    parser.add_argument("--admin-username", default="多动脑子z", help="Admin username for signing token.")
    parser.add_argument(
        "--admin-token",
        default=os.getenv("PARALLELLINES_ADMIN_ACCESS_TOKEN", ""),
        help="Session-backed admin access token. Prefer --admin-token-file to avoid shell history.",
    )
    parser.add_argument(
        "--admin-token-file",
        default=os.getenv("PARALLELLINES_ADMIN_TOKEN_FILE", ""),
        help="Path to a file containing a session-backed admin access token.",
    )
    parser.add_argument(
        "--admin-account",
        default=os.getenv("PARALLELLINES_ADMIN_ACCOUNT", ""),
        help="Admin account used to obtain a session-backed access token.",
    )
    parser.add_argument(
        "--admin-password",
        default=os.getenv("PARALLELLINES_ADMIN_PASSWORD", ""),
        help="Admin password used with --admin-account. Prefer environment variables.",
    )
    parser.add_argument(
        "--account",
        default=first_env("PARALLELLINES_NEWS_PUBLISH_ACCOUNT", "PARALLELLINES_PUBLISH_ACCOUNT"),
        help="Normal publisher account for public create-topic mode.",
    )
    parser.add_argument(
        "--password",
        default=first_env("PARALLELLINES_NEWS_PUBLISH_PASSWORD", "PARALLELLINES_PUBLISH_PASSWORD"),
        help="Publisher password used with --account. Prefer environment variables.",
    )
    parser.add_argument("--author-username", default="小小资讯", help="Topic author username.")
    parser.add_argument(
        "--ensure-author",
        action="store_true",
        help="Create the author as a normal user through migration import when missing.",
    )
    parser.add_argument("--author-email", default="", help="Author email used with --ensure-author.")
    parser.add_argument(
        "--author-display-name",
        default="",
        help="Author display name used with --ensure-author; defaults to username.",
    )
    parser.add_argument(
        "--author-avatar-file",
        default="apps/web/public/avatars/xiaoxiao-zixun.png",
        help="Optional avatar image to upload for the author after a successful --run publish.",
    )
    parser.add_argument(
        "--force-author-avatar",
        action="store_true",
        help="Upload the author avatar even when the public profile already has one.",
    )
    parser.add_argument("--board-slug", default="frontier", help="Target board slug.")
    parser.add_argument("--board-name", default="热点资讯", help="Target board display name.")
    parser.add_argument(
        "--board-description",
        default="自动汇集 AI 科技与社会热点，经人工审核后发布。",
        help="Board description used by migration payload when the board already exists.",
    )
    parser.add_argument("--board-color", default="#6366F1", help="Board color used by migration payload.")
    parser.add_argument("--external-id", default="", help="Optional stable migration external id.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Publish even if a recent same-title topic already exists in the board.",
    )
    parser.add_argument(
        "--source-prefix",
        default="manual-xiaoxiao-news",
        help="Migration source prefix; '-preview' is appended for dry-run preview.",
    )
    return parser.parse_args(argv)


# Decide which publishing path to use for this invocation.
# Key parameters are CLI args. Return value: "admin" or "public". Side effect: none.
def resolve_publish_mode(args: argparse.Namespace) -> str:
    if args.publish_mode != "auto":
        return args.publish_mode
    if args.admin_token or args.admin_token_file or (args.admin_account and args.admin_password):
        return "admin"
    if args.account and args.password:
        return "public"
    return "admin"


# Execute preview and, when requested, publish via the migration import API.
# Key parameter `argv` is optional CLI argv. Return value: process exit code. Side effect: API writes only with --run.
def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    body_path = Path(args.body_file)
    body = sys.stdin.read() if args.body_file == "-" else body_path.read_text(encoding="utf-8")
    if not body.strip():
        raise RuntimeError("Body is empty")
    if args.run:
        author_avatar_path(args)

    env_values = load_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/")
    mode = resolve_publish_mode(args)

    if mode == "public":
        if not args.account or not args.password:
            raise RuntimeError("Public publish mode requires --account/--password or PARALLELLINES_PUBLISH_* env vars")
        token = login_publisher_token(base_url, args.account, args.password)
        author_profile = validate_public_author_token(base_url, token, args.author_username)
        preview_data = build_public_preview(base_url, args, body, author_profile)
        print_public_result("Preview", preview_data)
        if int(preview_data.get("errors") or 0) > 0:
            raise RuntimeError("Preview returned errors; aborting")
        if not args.run:
            print("Preview only. Re-run with --run to publish.")
            return 0
        if not any(row.get("resource") == "topic" and row.get("action") == "created" for row in preview_data.get("rows") or []):
            raise RuntimeError("Preview did not create a topic; refusing to run")
        topic = create_public_topic(base_url, token, args, body)
        run_data = {
            "dry_run": False,
            "created": 1,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "rows": [
                {
                    "resource": "topic",
                    "key": args.title.strip(),
                    "action": "created",
                    "message": f"{topic.get('id')} {topic.get('share_url')}",
                }
            ],
        }
        print_public_result("Run", run_data)
        upload_author_avatar_with_public_token(base_url, args, token)
        verify_public_topic(base_url, args.title.strip())
        return 0

    token = resolve_admin_token(base_url, args, env_values)
    validate_admin_token(base_url, token)

    source_prefix = args.source_prefix.strip() or "manual-xiaoxiao-news"
    preview_payload = build_payload(args, body, source=f"{source_prefix}-preview")
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

    run_payload = build_payload(args, body, source=source_prefix)
    result = request_json(
        "POST",
        f"{base_url}/api/v1/admin/migrations/import/run",
        token=token,
        payload=run_payload,
    )
    print_import_result("Run", result)
    upload_author_avatar_if_requested(base_url, args, env_values)
    verify_public_topic(base_url, args.title.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
