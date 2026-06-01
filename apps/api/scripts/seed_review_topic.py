from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.forum import Board
from app.models.moderation import Reviewable
from app.models.user import User
from app.services.forum import (
    ADMIN_ONLY_TOPIC_BOARD_SLUGS,
    ForumService,
    board_display_order_expression,
    normalize_tag_name,
)
from app.services.moderation import ModerationService

DEFAULT_SEED_KEY = "seed-review-topic-v1"
DEFAULT_SEED_USERNAME = "seed_writer"
DEFAULT_SEED_EMAIL = "seed_writer@parallellines.local"
DEFAULT_DISPLAY_NAME = "种子作者"
DEFAULT_TITLE = "【种子审核测试】一个适合检查审核流的示例主题"
DEFAULT_BODY = """这是一篇由种子作者提交的示例内容，用来验证
「提交 → 进入审核队列 → 管理员批准 → 正式发布」流程。

## 预期检查点

- 执行脚本后，主题不会立刻出现在公开列表。
- 审核后台会出现一条待处理内容。
- 管理员批准后，主题会进入所选版块，并同步搜索索引和计数。
"""
DEFAULT_TAG = "种子内容"
SEED_REVIEW_SOURCE = "seed_content"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one seed author and queue one seed topic for moderation review."
    )
    parser.add_argument(
        "--board-slug",
        help="Target public board slug. Defaults to first writable public board.",
    )
    parser.add_argument("--seed-username", default=DEFAULT_SEED_USERNAME)
    parser.add_argument("--seed-email", default=DEFAULT_SEED_EMAIL)
    parser.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    parser.add_argument(
        "--seed-key",
        default=DEFAULT_SEED_KEY,
        help="Idempotency key stored in reviewable data.",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--body", default=DEFAULT_BODY)
    parser.add_argument(
        "--tags",
        help="Comma-separated tags. Defaults to board-required/allowed tags or 种子内容.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create another reviewable even if seed-key exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without writing database rows.",
    )
    return parser.parse_args(argv)


async def async_main(argv: Sequence[str] | None = None) -> None:
    configure_logging()
    args = parse_args(argv)
    async with AsyncSessionLocal() as session:
        result = await queue_seed_topic(session, args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


async def queue_seed_topic(session: AsyncSession, args: argparse.Namespace) -> dict[str, object]:
    board = await select_target_board(session, args.board_slug)
    tags = select_topic_tags(board, args.tags)
    ForumService(session)._validate_board_topic_tags(board, tags)

    if args.dry_run:
        return {
            "dry_run": True,
            "would_create": {
                "seed_username": args.seed_username,
                "seed_email": args.seed_email,
                "board_slug": board.slug,
                "board_name": board.name,
                "title": args.title,
                "tags": tags,
                "review_source": SEED_REVIEW_SOURCE,
            },
        }

    author, author_created = await upsert_seed_author(
        session,
        username=args.seed_username,
        email=args.seed_email,
        display_name=args.display_name,
    )
    existing = None if args.force else await find_existing_seed_reviewable(
        session,
        author=author,
        board=board,
        seed_key=args.seed_key,
    )
    if existing is not None:
        await session.commit()
        return reviewable_result(
            existing,
            author=author,
            board=board,
            author_created=author_created,
            created=False,
        )

    reviewable = await ModerationService(session).create_content_reviewable(
        current_user=author,
        reviewable_type="queued_topic",
        board=board,
        sanitized_fields={"title": args.title, "raw_md": args.body},
        matched_fields=("seed_author_requires_review",),
        data={
            "title": args.title,
            "raw_md": args.body,
            "tags": tags,
            "pinned": False,
            "featured": False,
            "board_slug": board.slug,
            "seed_key": args.seed_key,
            "seed_author": True,
        },
        source=SEED_REVIEW_SOURCE,
        source_summary="种子作者提交的内容，需要审核通过后才会公开。",
    )
    await session.commit()
    return reviewable_result(
        reviewable,
        author=author,
        board=board,
        author_created=author_created,
        created=True,
    )


async def select_target_board(session: AsyncSession, board_slug: str | None) -> Board:
    if board_slug:
        board = await session.scalar(select(Board).where(Board.slug == board_slug))
        if board is None:
            raise RuntimeError(f"Board not found: {board_slug}")
        if board.visibility != "public":
            raise RuntimeError(f"Seed topic target must be a public board: {board.slug}")
        if board.slug in ADMIN_ONLY_TOPIC_BOARD_SLUGS:
            raise RuntimeError(
                f"Seed author cannot create topics in admin-only board: {board.slug}"
            )
        return board

    board = await session.scalar(
        select(Board)
        .where(Board.visibility == "public", Board.slug.not_in(ADMIN_ONLY_TOPIC_BOARD_SLUGS))
        .order_by(board_display_order_expression(), desc(Board.topic_count), Board.name)
        .limit(1)
    )
    if board is None:
        raise RuntimeError("No public writable board found. Create a public board first.")
    return board


async def upsert_seed_author(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    display_name: str,
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    existing = await session.scalar(
        select(User).where(or_(User.username == username, User.email == normalized_email))
    )
    if existing is not None:
        if existing.username != username or existing.email != normalized_email:
            raise RuntimeError(
                "Seed username/email conflicts with an existing different user: "
                f"id={existing.id}, username={existing.username}, email={existing.email}"
            )
        existing.display_name = display_name
        existing.status = "active"
        existing.role = "user"
        return existing, False

    user = User(
        username=username,
        email=normalized_email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        display_name=display_name,
        bio="用于内容填充和审核流验证的种子作者。",
        role="user",
        status="active",
    )
    session.add(user)
    await session.flush()
    return user, True


async def find_existing_seed_reviewable(
    session: AsyncSession,
    *,
    author: User,
    board: Board,
    seed_key: str,
) -> Reviewable | None:
    reviewables = list(
        await session.scalars(
            select(Reviewable)
            .where(
                Reviewable.type == "queued_topic",
                Reviewable.source == SEED_REVIEW_SOURCE,
                Reviewable.created_by_id == author.id,
                Reviewable.board_id == board.id,
            )
            .order_by(desc(Reviewable.created_at))
            .limit(50)
        )
    )
    return next(
        (reviewable for reviewable in reviewables if reviewable.data.get("seed_key") == seed_key),
        None,
    )


def select_topic_tags(board: Board, tags_arg: str | None) -> list[str]:
    if tags_arg:
        return normalized_unique_tags(tags_arg.split(","))

    required_tags = normalized_unique_tags(board.required_tags or [])
    if required_tags:
        return required_tags

    allowed_tags = normalized_unique_tags(board.allowed_tags or [])
    if allowed_tags:
        return allowed_tags[:1]

    return [normalize_tag_name(DEFAULT_TAG)]


def normalized_unique_tags(values: Sequence[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        tag = normalize_tag_name(value)
        if tag and tag not in tags:
            tags.append(tag[:48])
    return tags[:8]


def reviewable_result(
    reviewable: Reviewable,
    *,
    author: User,
    board: Board,
    author_created: bool,
    created: bool,
) -> dict[str, object]:
    return {
        "created": created,
        "author_created": author_created,
        "seed_author": {
            "id": author.id,
            "username": author.username,
            "email": author.email,
            "display_name": author.display_name,
        },
        "board": {
            "id": board.id,
            "slug": board.slug,
            "name": board.name,
        },
        "reviewable": {
            "id": reviewable.id,
            "type": reviewable.type,
            "status": reviewable.status,
            "source": reviewable.source,
            "seed_key": reviewable.data.get("seed_key"),
            "title": reviewable.data.get("title"),
            "tags": reviewable.data.get("tags"),
        },
        "next_step": (
            "Open the moderation reviewables queue, then approve this reviewable to publish "
            "the queued topic."
        ),
    }


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
