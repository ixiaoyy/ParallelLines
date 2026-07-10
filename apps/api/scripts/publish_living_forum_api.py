from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.services.living_forum import (  # noqa: E402
    PERSONAS,
    LivingForumTopicPlan,
    build_living_forum_day,
    engagement_reason_for_activity,
    engagement_reply_body_for_activity,
    engagement_responder_for_activity,
    fallback_living_forum_responder,
    local_today,
)

API_USER_AGENT = "ParallelLinesLivingForumPublisher/1.0"
DEFAULT_SITE_URL = "https://www.pingxingxian.space"
DEFAULT_SOURCE_PREFIX = "living-forum"
MIGRATION_SOURCE_LIMIT = 80
DEFAULT_PERSONA_PASSWORD_ENV = "PARALLELLINES_LIVING_PERSONA_PASSWORD"
DEFAULT_PERSONA_PASSWORD = "oldhuai123"

BOARD_DEFAULTS: dict[str, dict[str, str]] = {
    "frontier": {
        "name": "热点资讯",
        "description": "自动汇集 AI 科技与社会热点，经人工审核后发布。",
        "color": "#6366F1",
    },
    "lounge": {
        "name": "闲聊茶馆",
        "description": "轻松聊天、日常分享、兴趣交流和不那么严肃的话题。",
        "color": "#8B5CF6",
    },
    "qna": {
        "name": "有问必答",
        "description": "有困惑就提出来，带上背景，大家一起帮你理清。",
        "color": "#65A30D",
    },
    "resources": {
        "name": "资源荟萃",
        "description": "收集值得收藏的工具、资料、网站、课程和内容。",
        "color": "#F97316",
    },
    "reading": {
        "name": "读书感悟",
        "description": "分享读书摘记、阅读心得、金句摘录与文字感悟。",
        "color": "#DB2777",
    },
}

PERSONA_PUBLIC_CREDENTIAL_ENVS: dict[str, tuple[tuple[str, str], ...]] = {
    "小小资讯": (
        ("PARALLELLINES_NEWS_PUBLISH_ACCOUNT", "PARALLELLINES_NEWS_PUBLISH_PASSWORD"),
        ("PARALLELLINES_PUBLISH_ACCOUNT", "PARALLELLINES_PUBLISH_PASSWORD"),
    ),
    "老槐": (
        ("PARALLELLINES_LIVING_OLD_HUAI_ACCOUNT", "PARALLELLINES_LIVING_OLD_HUAI_PASSWORD"),
    ),
    "远山便利店": (
        ("PARALLELLINES_LIVING_YUANSHAN_ACCOUNT", "PARALLELLINES_LIVING_YUANSHAN_PASSWORD"),
    ),
    "雾里看山": (("PARALLELLINES_LIVING_FOG_ACCOUNT", "PARALLELLINES_LIVING_FOG_PASSWORD"),),
    "rain_404": (
        ("PARALLELLINES_LIVING_RAIN404_ACCOUNT", "PARALLELLINES_LIVING_RAIN404_PASSWORD"),
    ),
}

UNIFIED_PUBLIC_CREDENTIAL_ENVS: tuple[tuple[str, str], ...] = (
    ("PARALLELLINES_LIVING_PUBLISH_ACCOUNT", "PARALLELLINES_LIVING_PUBLISH_PASSWORD"),
    ("PARALLELLINES_NEWS_PUBLISH_ACCOUNT", "PARALLELLINES_NEWS_PUBLISH_PASSWORD"),
    ("PARALLELLINES_PUBLISH_ACCOUNT", "PARALLELLINES_PUBLISH_PASSWORD"),
)


@dataclass(frozen=True)
class PublicCredential:
    """Store one persona's public API login source without exposing the secret."""

    username: str
    account: str
    password: str
    account_env: str
    password_env: str


def project_root() -> Path:
    """Resolve the ParallelLines repository root from this API script."""

    return Path(__file__).resolve().parents[3]


def load_local_publisher_env() -> None:
    """Load ignored local publishing credentials without printing secret values."""

    env_path = project_root() / ".tmp" / "frontier-publisher.env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def first_env(*names: str) -> str:
    """Return the first non-empty environment variable value in priority order."""

    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def public_credential_for_persona(username: str) -> PublicCredential | None:
    """Return configured public API credentials for one persona, if present."""

    for account_env, password_env in PERSONA_PUBLIC_CREDENTIAL_ENVS.get(username, ()):
        account = os.getenv(account_env, "").strip()
        password = os.getenv(password_env, "").strip()
        if account and password:
            return PublicCredential(
                username=username,
                account=account,
                password=password,
                account_env=account_env,
                password_env=password_env,
            )
    if username in PERSONAS:
        password = os.getenv(DEFAULT_PERSONA_PASSWORD_ENV, DEFAULT_PERSONA_PASSWORD).strip()
        if password:
            return PublicCredential(
                username=username,
                account=username,
                password=password,
                account_env="username",
                password_env=DEFAULT_PERSONA_PASSWORD_ENV,
            )
    return None


def unified_public_credential(username: str) -> PublicCredential | None:
    """Return the shared public API credential used for cold-start publishing."""

    for account_env, password_env in UNIFIED_PUBLIC_CREDENTIAL_ENVS:
        account = os.getenv(account_env, "").strip()
        password = os.getenv(password_env, "").strip()
        if account and password:
            return PublicCredential(
                username=username,
                account=account,
                password=password,
                account_env=account_env,
                password_env=password_env,
            )
    return None


def public_credentials_for_plans(
    plans: Sequence[LivingForumTopicPlan],
    *,
    author_mode: str = "mapped",
    unified_username: str = "小小资讯",
) -> dict[str, PublicCredential]:
    """Return public credentials for every planned author/responder that has them."""

    usernames = {plan.author for plan in plans}
    for plan in plans:
        responder = engagement_responder_for_activity(plan.activity_type)
        if responder == plan.author:
            responder = fallback_living_forum_responder(responder)
        usernames.add(responder)
    if author_mode == "unified":
        credential = unified_public_credential(unified_username)
        return {username: credential for username in usernames} if credential is not None else {}

    credentials: dict[str, PublicCredential] = {}
    for username in sorted(usernames):
        credential = public_credential_for_persona(username)
        if credential is not None:
            credentials[username] = credential
    return credentials


def load_env(path: Path) -> dict[str, str]:
    """Read a simple KEY=VALUE env file and return parsed values."""

    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def normalize_site_url(value: str) -> str:
    """Normalize a site URL or `/api/v1` URL to the public site root."""

    base_url = value.strip().rstrip("/")
    if base_url.endswith("/api/v1"):
        return base_url[: -len("/api/v1")]
    return base_url


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Send one JSON API request and return the decoded response envelope."""

    body = None
    headers = {"Accept": "application/json", "User-Agent": API_USER_AGENT}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured site URL.
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {error_body[:800]}") from exc
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed for {url}: {exc}") from exc
    return json.loads(response_body or "{}")


def public_user_id(site_url: str, username: str, *, expected_role: str | None = None) -> str:
    """Resolve a public user id and optionally validate its role."""

    response = request_json("GET", f"{site_url}/api/v1/users/{quote(username)}", timeout=20)
    data = dict(response.get("data") or {})
    if expected_role and data.get("role") != expected_role:
        raise RuntimeError(f"{username} role is {data.get('role')!r}, expected {expected_role!r}")
    user_id = str(data.get("id") or "")
    if not user_id:
        raise RuntimeError(f"Could not resolve user id for {username}")
    return user_id


def make_admin_token(admin_id: str, env_values: dict[str, str]) -> str:
    """Build a short-lived admin access token from local API JWT settings."""

    secret = env_values.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is missing; provide --admin-token-file or admin login")
    algorithm = env_values.get("JWT_ALGORITHM") or "HS256"
    now = datetime.now(UTC)
    payload = {
        "sub": admin_id,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def login_admin_token(site_url: str, account: str, password: str) -> str:
    """Log in with an admin account and return its session-backed access token."""

    response = request_json(
        "POST",
        f"{site_url}/api/v1/auth/login",
        payload={"account": account, "password": password},
    )
    data = dict(response.get("data") or {})
    if data.get("two_factor_required"):
        raise RuntimeError("Admin account has 2FA enabled; use --admin-token-file")
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("Admin login succeeded without an access token")
    return token


def login_public_token(site_url: str, credential: PublicCredential) -> str:
    """Log in with one persona's public account and return its access token."""

    response = request_json(
        "POST",
        f"{site_url}/api/v1/auth/login",
        payload={"account": credential.account, "password": credential.password},
    )
    data = dict(response.get("data") or {})
    if data.get("two_factor_required"):
        raise RuntimeError(
            f"{credential.username} has 2FA enabled; public fallback cannot use this account"
        )
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError(f"{credential.username} login succeeded without an access token")
    return token


def validate_public_token(site_url: str, token: str, expected_username: str) -> dict[str, Any]:
    """Return the authenticated profile after verifying the expected persona username."""

    response = request_json("GET", f"{site_url}/api/v1/auth/me", token=token, timeout=20)
    data = dict(response.get("data") or {})
    username = str(data.get("username") or "")
    if username != expected_username:
        raise RuntimeError(
            f"Public credential logged in as {username or '<unknown>'!r}, "
            f"expected {expected_username!r}"
        )
    if data.get("status") != "active":
        raise RuntimeError(f"Public account {expected_username!r} is not active")
    return data


def resolve_admin_token(
    site_url: str,
    args: argparse.Namespace,
    env_values: dict[str, str],
) -> str:
    """Resolve an admin token from CLI, env, login credentials, or local JWT settings."""

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
        return login_admin_token(site_url, args.admin_account, args.admin_password)
    admin_id = public_user_id(site_url, args.admin_username, expected_role="admin")
    return make_admin_token(admin_id, env_values)


def validate_admin_token(site_url: str, token: str) -> None:
    """Confirm the token belongs to an active admin before migration writes."""

    response = request_json("GET", f"{site_url}/api/v1/auth/me", token=token, timeout=20)
    data = dict(response.get("data") or {})
    if data.get("role") != "admin":
        raise RuntimeError(f"Authenticated token role is {data.get('role')!r}, expected 'admin'")


def resolve_valid_admin_token(
    site_url: str,
    args: argparse.Namespace,
    env_values: dict[str, str],
) -> str:
    """Resolve and validate an admin token, retrying login when an env token is stale."""

    token = resolve_admin_token(site_url, args, env_values)
    try:
        validate_admin_token(site_url, token)
    except RuntimeError as exc:
        has_stale_token = bool(args.admin_token or args.admin_token_file)
        if args.admin_account and args.admin_password and has_stale_token:
            print("Admin token rejected; retrying with configured admin login.")
            token = login_admin_token(site_url, args.admin_account, args.admin_password)
            validate_admin_token(site_url, token)
            return token
        raise RuntimeError(
            "Admin authentication failed. Refresh PARALLELLINES_ADMIN_ACCESS_TOKEN, "
            "set PARALLELLINES_ADMIN_ACCOUNT/PARALLELLINES_ADMIN_PASSWORD, or pass "
            "--admin-token-file."
        ) from exc
    return token


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI options for the HTTP migration publisher."""

    load_local_publisher_env()
    parser = argparse.ArgumentParser(
        description=(
            "Preview or publish living-forum daily programs through the admin migration API."
        )
    )
    parser.add_argument(
        "--date",
        dest="planned_date",
        help="Local Asia/Shanghai date in YYYY-MM-DD format; defaults to today.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum daily topics to generate.")
    parser.add_argument(
        "--reply-limit",
        type=int,
        default=2,
        help="Maximum first-wave persona replies to include; use 0 to disable replies.",
    )
    parser.add_argument(
        "--base-url",
        default=first_env("PARALLELLINES_SITE_URL", "PARALLELLINES_API_BASE_URL")
        or DEFAULT_SITE_URL,
        help="Public site root or /api/v1 URL.",
    )
    parser.add_argument(
        "--env-file",
        default=str(project_root() / "apps/api/.env"),
        help="Optional API .env used only for the legacy local JWT signer.",
    )
    parser.add_argument(
        "--publish-mode",
        choices=("auto", "admin", "public"),
        default="auto",
        help="Use admin migration import or normal public topic/reply APIs.",
    )
    parser.add_argument(
        "--public-author-mode",
        choices=("unified", "mapped"),
        default="mapped",
        help="Public mode: use one shared account or require per-persona credentials.",
    )
    parser.add_argument(
        "--public-author-username",
        default=os.getenv("PARALLELLINES_PUBLIC_AUTHOR_USERNAME", "小小资讯"),
        help="Expected username for the shared public publishing account.",
    )
    parser.add_argument(
        "--api-preview",
        action="store_true",
        help="Call the remote migration preview API after local payload generation.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Import the payload after a clean API preview.",
    )
    parser.add_argument(
        "--print-payload",
        action="store_true",
        help="Print the full migration JSON payload after the compact local summary.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Public mode: create topics even when a recent same-title topic exists.",
    )
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
        "--admin-username",
        default=os.getenv("PARALLELLINES_ADMIN_USERNAME", "多动脑子z"),
        help="Admin username used by the legacy local JWT signer fallback.",
    )
    parser.add_argument(
        "--source-prefix",
        default=DEFAULT_SOURCE_PREFIX,
        help="Migration source prefix; the local date and preview/run suffix are appended.",
    )
    return parser.parse_args(argv)


def parse_planned_date(value: str | None) -> date:
    """Convert an optional ISO date argument into the local planned date."""

    return date.fromisoformat(value) if value else local_today()


def build_migration_payload(
    plans: Sequence[LivingForumTopicPlan],
    *,
    reply_limit: int,
    source: str,
) -> dict[str, Any]:
    """Convert daily program plans into the admin migration import format."""

    reply_records = migration_reply_records(plans, reply_limit=reply_limit)
    used_authors = {plan.author for plan in plans}
    used_authors.update(str(record["author_username"]) for record in reply_records)
    return {
        "source": source,
        "users": persona_user_records(used_authors),
        "boards": board_records(plan.board_slug for plan in plans),
        "topics": [migration_topic_record(plan) for plan in plans],
        "posts": reply_records,
    }


def persona_user_records(usernames: Iterable[str]) -> list[dict[str, object]]:
    """Build migration user records for all persona accounts used by the payload."""

    records: list[dict[str, object]] = []
    seen = set(usernames)
    for username, persona in PERSONAS.items():
        if username not in seen:
            continue
        records.append(
            {
                "username": persona.username,
                "email": persona.email,
                "display_name": persona.username,
                "is_persona": True,
            }
        )
    return records


def board_records(board_slugs: Iterable[str]) -> list[dict[str, str]]:
    """Build migration board records for every target board in first-seen order."""

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for board_slug in board_slugs:
        if board_slug in seen:
            continue
        seen.add(board_slug)
        defaults = BOARD_DEFAULTS.get(
            board_slug,
            {
                "name": board_slug,
                "description": "Imported board",
                "color": "#409EFF",
            },
        )
        records.append({"slug": board_slug, **defaults})
    return records


def migration_topic_record(plan: LivingForumTopicPlan) -> dict[str, Any]:
    """Build one migration topic record from a living-forum plan."""

    return {
        "external_id": plan.seed_key,
        "board_slug": plan.board_slug,
        "author_username": plan.author,
        "title": plan.title,
        "slug": stable_plan_slug(plan),
        "tags": list(plan.tags),
        "raw_md": body_with_poll_prompt(plan),
    }


def migration_reply_records(
    plans: Sequence[LivingForumTopicPlan],
    *,
    reply_limit: int,
) -> list[dict[str, Any]]:
    """Build first-wave persona reply records for the first planned topics."""

    records: list[dict[str, Any]] = []
    for plan in plans:
        if len(records) >= max(0, reply_limit):
            break
        responder = engagement_responder_for_activity(plan.activity_type)
        if responder == plan.author:
            responder = fallback_living_forum_responder(responder)
        raw_md = engagement_reply_body_for_activity(plan.activity_type, plan.title)
        reason = engagement_reason_for_activity(plan.activity_type, plan.interaction_mode)
        records.append(
            {
                "topic_external_id": plan.seed_key,
                "board_slug": plan.board_slug,
                "author_username": responder,
                "post_number": 2,
                "raw_md": f"{raw_md}\n\n> 自动首评：{reason}",
            }
        )
    return records


def body_with_poll_prompt(plan: LivingForumTopicPlan) -> str:
    """Return Markdown body text, converting planned polls into replyable prompts."""

    body = plan.raw_md.strip()
    if plan.poll is None:
        return body
    options = "\n".join(f"- [ ] {option}" for option in plan.poll.options)
    return (
        f"{body}\n\n"
        "---\n\n"
        f"**{plan.poll.question}**\n\n"
        f"{options}\n\n"
        "> 这个帖子通过迁移导入发布，投票先以清单形式呈现；直接回复你的选择也算数。"
    )


def stable_plan_slug(plan: LivingForumTopicPlan) -> str:
    """Return a deterministic ASCII slug that migration imports can reuse."""

    seed = plan.seed_key.removeprefix("living:")
    slug = re.sub(r"[^a-z0-9]+", "-", seed.lower()).strip("-")
    return f"living-{slug}"[:180]


def source_name(prefix: str, planned_date: date, *, preview: bool) -> str:
    """Build a migration source name that stays inside the API schema limit."""

    suffix = "preview" if preview else "run"
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", prefix.strip()) or DEFAULT_SOURCE_PREFIX
    return f"{safe_prefix}:{planned_date.isoformat()}:{suffix}"[:MIGRATION_SOURCE_LIMIT]


def print_payload_summary(
    plans: Sequence[LivingForumTopicPlan],
    payload: dict[str, Any],
    *,
    site_url: str,
) -> None:
    """Print a compact local preview without dumping credentials or full bodies."""

    print(
        "Local preview: "
        f"site={site_url} source={payload['source']} users={len(payload['users'])} "
        f"boards={len(payload['boards'])} topics={len(payload['topics'])} "
        f"replies={len(payload['posts'])}"
    )
    for index, plan in enumerate(plans, start=1):
        poll_marker = " poll-as-markdown" if plan.poll else ""
        source_marker = f" source={plan.source_name}" if plan.source_name else ""
        print(
            f"- topic {index}: [{plan.board_slug}] {plan.author} "
            f"{stable_plan_slug(plan)}{poll_marker}{source_marker} :: {plan.title}"
        )
    for post in payload["posts"]:
        print(
            f"- reply: {post['author_username']} -> {post['topic_external_id']} "
            f"post_number={post['post_number']}"
        )


def print_import_result(label: str, response: dict[str, Any]) -> None:
    """Print a compact migration API result without exposing tokens."""

    data = dict(response.get("data") or {})
    print(
        f"{label}: dry_run={data.get('dry_run')} created={data.get('created')} "
        f"updated={data.get('updated')} skipped={data.get('skipped')} errors={data.get('errors')}"
    )
    for row in data.get("rows") or []:
        print(
            f"- {row.get('resource')} {row.get('key')}: "
            f"{row.get('action')} ({row.get('message')})"
        )


def assert_clean_preview(response: dict[str, Any]) -> None:
    """Raise when the migration preview reports row-level errors."""

    data = dict(response.get("data") or {})
    if int(data.get("errors") or 0) > 0:
        raise RuntimeError("API preview returned errors; aborting run")


def has_admin_configuration(args: argparse.Namespace) -> bool:
    """Return whether explicit admin credentials are configured for this invocation."""

    return bool(
        args.admin_token
        or args.admin_token_file
        or (args.admin_account and args.admin_password)
    )


def resolve_publish_mode(args: argparse.Namespace, plans: Sequence[LivingForumTopicPlan]) -> str:
    """Choose admin migration mode or public fallback mode from available credentials."""

    if args.publish_mode != "auto":
        return str(args.publish_mode)
    if has_admin_configuration(args):
        return "admin"
    if public_credentials_for_plans(
        plans,
        author_mode=args.public_author_mode,
        unified_username=args.public_author_username,
    ):
        return "public"
    return "admin"


def topic_create_payload(plan: LivingForumTopicPlan, *, include_poll: bool) -> dict[str, Any]:
    """Build the normal public create-topic payload for one plan."""

    payload: dict[str, Any] = {
        "title": plan.title,
        "raw_md": plan.raw_md.strip(),
        "tags": list(plan.tags),
        "pinned": False,
        "featured": False,
    }
    if include_poll and plan.poll is not None:
        from app.services.living_forum import poll_close_time

        payload["poll"] = {
            "question": plan.poll.question,
            "options": list(plan.poll.options),
            "multiple_choice": plan.poll.multiple_choice,
            "closes_at": poll_close_time(plan.planned_date).isoformat(),
        }
    return payload


def recent_board_topics(site_url: str, board_slug: str) -> list[dict[str, Any]]:
    """Return recent public topics from one board for duplicate detection."""

    query = urlencode({"sort": "latest", "limit": 30})
    response = request_json(
        "GET",
        f"{site_url}/api/v1/boards/{quote(board_slug)}/topics?{query}",
        timeout=20,
    )
    return [dict(item) for item in response.get("data") or []]


def find_recent_same_title_topic(
    site_url: str,
    board_slug: str,
    title: str,
) -> dict[str, Any] | None:
    """Return a recent same-title topic in a board, if one is visible."""

    for topic in recent_board_topics(site_url, board_slug):
        if str(topic.get("title") or "") == title:
            return topic
    return None


def public_topic_posts(site_url: str, topic_id: str) -> list[dict[str, Any]]:
    """Return visible posts for a topic so public fallback can avoid duplicate replies."""

    query = urlencode({"sort": "chronological"})
    response = request_json("GET", f"{site_url}/api/v1/topics/{quote(topic_id)}/posts?{query}")
    return [dict(item) for item in response.get("data") or []]


def find_matching_public_reply(
    site_url: str,
    topic_id: str,
    *,
    author: str,
    raw_md: str,
) -> dict[str, Any] | None:
    """Return an existing same-author same-body reply, if it already exists."""

    for post in public_topic_posts(site_url, topic_id):
        if post.get("author_name") == author and str(post.get("raw_md") or "") == raw_md:
            return post
    return None


def create_public_topic(
    site_url: str,
    token: str,
    plan: LivingForumTopicPlan,
) -> dict[str, Any]:
    """Create one topic through the normal public board topic API."""

    response = request_json(
        "POST",
        f"{site_url}/api/v1/boards/{quote(plan.board_slug)}/topics",
        token=token,
        payload=topic_create_payload(plan, include_poll=True),
    )
    return dict(response.get("data") or {})


def create_public_reply(site_url: str, token: str, topic_id: str, raw_md: str) -> dict[str, Any]:
    """Create one reply through the normal public topic posts API."""

    response = request_json(
        "POST",
        f"{site_url}/api/v1/topics/{quote(topic_id)}/posts",
        token=token,
        payload={"raw_md": raw_md},
    )
    return dict(response.get("data") or {})


def public_topic_url(site_url: str, topic: dict[str, Any]) -> str:
    """Return a printable absolute URL for a topic-like API object."""

    share_url = str(topic.get("share_url") or "")
    return f"{site_url}{share_url}" if share_url.startswith("/") else share_url


def run_public_api_mode(
    site_url: str,
    args: argparse.Namespace,
    plans: Sequence[LivingForumTopicPlan],
) -> int:
    """Preview or publish through ordinary persona public APIs."""

    credentials = public_credentials_for_plans(
        plans,
        author_mode=args.public_author_mode,
        unified_username=args.public_author_username,
    )
    if not credentials:
        raise RuntimeError(
            "No public persona credentials are configured. Add admin credentials for "
            "migration import or set persona public account env vars."
        )
    token_cache: dict[str, str] = {}
    topic_ids_by_seed: dict[str, str] = {}
    if args.public_author_mode == "unified":
        print(
            "Public API mode: using one shared public account; "
            "planned personas remain content labels only."
        )
    else:
        print("Public API mode: using mapped persona accounts; migration rows are not imported.")

    for plan in plans:
        credential = credentials.get(plan.author)
        if credential is None:
            print(f"- topic skipped: {plan.author} has no public credential :: {plan.title}")
            continue
        try:
            token = public_token_for_credential(site_url, credential, token_cache)
        except RuntimeError as exc:
            print(f"- topic skipped: {plan.author} credential rejected ({exc}) :: {plan.title}")
            continue
        existing = None if args.force else find_recent_same_title_topic(
            site_url, plan.board_slug, plan.title
        )
        if existing is not None:
            topic_id = str(existing.get("id") or "")
            if topic_id:
                topic_ids_by_seed[plan.seed_key] = topic_id
            print(
                f"- topic existing: as {credential.username} "
                f"for {plan.author} :: {public_topic_url(site_url, existing)}"
            )
            continue
        if not args.run:
            poll_marker = " real-poll" if plan.poll else ""
            print(
                f"- topic would create{poll_marker}: "
                f"[{plan.board_slug}] as {credential.username} for {plan.author} :: {plan.title}"
            )
            continue
        topic = create_public_topic(site_url, token, plan)
        topic_id = str(topic.get("id") or "")
        if topic_id:
            topic_ids_by_seed[plan.seed_key] = topic_id
        print(
            f"- topic created: as {credential.username} "
            f"for {plan.author} :: {public_topic_url(site_url, topic)}"
        )

    run_public_replies(site_url, args, plans, credentials, token_cache, topic_ids_by_seed)
    if not args.run:
        print("Public API preview only. Re-run with --run to create available topics/replies.")
    return 0


def public_token_for_credential(
    site_url: str,
    credential: PublicCredential,
    token_cache: dict[str, str],
) -> str:
    """Return a validated public token, logging in only once per persona."""

    cached = token_cache.get(credential.username)
    if cached:
        return cached
    token = login_public_token(site_url, credential)
    validate_public_token(site_url, token, credential.username)
    token_cache[credential.username] = token
    return token


def run_public_replies(
    site_url: str,
    args: argparse.Namespace,
    plans: Sequence[LivingForumTopicPlan],
    credentials: dict[str, PublicCredential],
    token_cache: dict[str, str],
    topic_ids_by_seed: dict[str, str],
) -> None:
    """Preview or create first-wave public persona replies for available topics."""

    reply_count = 0
    for plan in plans:
        if reply_count >= max(0, args.reply_limit):
            break
        responder = engagement_responder_for_activity(plan.activity_type)
        if responder == plan.author:
            responder = fallback_living_forum_responder(responder)
        raw_md = engagement_reply_body_for_activity(plan.activity_type, plan.title)
        reason = engagement_reason_for_activity(plan.activity_type, plan.interaction_mode)
        raw_md = f"{raw_md}\n\n> 自动首评：{reason}"
        credential = credentials.get(responder)
        if credential is None:
            print(f"- reply skipped: {responder} has no public credential -> {plan.seed_key}")
            continue
        try:
            token = public_token_for_credential(site_url, credential, token_cache)
        except RuntimeError as exc:
            print(f"- reply skipped: {responder} credential rejected ({exc}) -> {plan.seed_key}")
            continue
        topic_id = topic_ids_by_seed.get(plan.seed_key)
        if not topic_id:
            print(f"- reply pending: topic not available yet -> {plan.seed_key}")
            continue
        existing = find_matching_public_reply(
            site_url,
            topic_id,
            author=credential.username,
            raw_md=raw_md,
        )
        if existing is not None:
            print(f"- reply existing: as {credential.username} for {responder} -> topic {topic_id}")
            reply_count += 1
            continue
        if not args.run:
            print(
                f"- reply would create: as {credential.username} "
                f"for {responder} -> topic {topic_id}"
            )
            reply_count += 1
            continue
        post = create_public_reply(site_url, token, topic_id, raw_md)
        print(
            f"- reply created: as {credential.username} "
            f"for {responder} -> {post.get('share_url')}"
        )
        reply_count += 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local preview, optional API preview, and optional import."""

    args = parse_args(argv)
    planned_date = parse_planned_date(args.planned_date)
    site_url = normalize_site_url(args.base_url)
    local_source = source_name(args.source_prefix, planned_date, preview=True)
    plans = build_living_forum_day(planned_date, limit=args.limit)
    payload = build_migration_payload(plans, reply_limit=args.reply_limit, source=local_source)
    print_payload_summary(plans, payload, site_url=site_url)
    if args.print_payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.flush()

    if not args.api_preview and not args.run:
        print("Local preview only. Add --api-preview to ask the site, or --run to import.")
        return 0

    mode = resolve_publish_mode(args, plans)
    if mode == "public":
        return run_public_api_mode(site_url, args, plans)

    env_values = load_env(Path(args.env_file))
    token = resolve_valid_admin_token(site_url, args, env_values)

    preview = request_json(
        "POST",
        f"{site_url}/api/v1/admin/migrations/import/preview",
        token=token,
        payload=payload,
    )
    print_import_result("API preview", preview)
    assert_clean_preview(preview)
    if not args.run:
        print("API preview only. Re-run with --run to import.")
        return 0

    run_payload = build_migration_payload(
        plans,
        reply_limit=args.reply_limit,
        source=source_name(args.source_prefix, planned_date, preview=False),
    )
    result = request_json(
        "POST",
        f"{site_url}/api/v1/admin/migrations/import/run",
        token=token,
        payload=run_payload,
    )
    print_import_result("Run", result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
