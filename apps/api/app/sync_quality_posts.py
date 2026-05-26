from __future__ import annotations

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.services.quality_posts import sync_quality_posts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize pinned quality posts into the current database."
    )
    parser.add_argument("--board-slug", default="announcements")
    parser.add_argument("--author-username", default=None)
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    configure_logging()
    logger = get_logger("quality_posts")
    async with AsyncSessionLocal() as session:
        topics = await sync_quality_posts(
            session,
            board_slug=args.board_slug,
            author_username=args.author_username,
        )
    logger.info(
        "quality_posts_synced",
        count=len(topics),
        topic_ids=[topic.id for topic in topics],
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
