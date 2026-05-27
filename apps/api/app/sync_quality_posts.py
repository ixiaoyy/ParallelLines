from __future__ import annotations

import argparse
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.services.quality_posts import QUALITY_POST_AUTHOR_USERNAME, sync_quality_posts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize official guide posts into the announcements board."
    )
    parser.add_argument("--board-slug", default="announcements")
    parser.add_argument("--author-username", default=QUALITY_POST_AUTHOR_USERNAME)
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    configure_logging()
    logger = get_logger("featured_posts")
    async with AsyncSessionLocal() as session:
        topics = await sync_quality_posts(
            session,
            board_slug=args.board_slug,
            author_username=args.author_username,
        )
    logger.info(
        "featured_posts_synced",
        count=len(topics),
        topic_ids=[topic.id for topic in topics],
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
