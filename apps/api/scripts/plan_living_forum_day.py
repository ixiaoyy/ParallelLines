from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.services.living_forum import LivingForumService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI options for the living-forum daily program runner."""

    parser = argparse.ArgumentParser(
        description="Preview or publish the daily AI-operated ParallelLines program."
    )
    parser.add_argument("--run", action="store_true", help="Publish today's program.")
    parser.add_argument(
        "--engage",
        action="store_true",
        help="Also preview or write persona replies for published living-forum topics.",
    )
    parser.add_argument(
        "--engage-only",
        action="store_true",
        help="Skip topic planning/publishing and only preview or write persona replies.",
    )
    parser.add_argument(
        "--date",
        dest="planned_date",
        help="Local Asia/Shanghai date in YYYY-MM-DD format; defaults to today.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum topics to plan/publish.")
    parser.add_argument(
        "--reply-limit",
        type=int,
        default=None,
        help="Maximum persona replies to preview/write for the day.",
    )
    parser.add_argument(
        "--publish-mode",
        choices=("auto", "review", "sample_review", "off"),
        default=None,
        help="Override LIVING_FORUM_PUBLISH_MODE for this run.",
    )
    return parser.parse_args(argv)


async def async_main(argv: Sequence[str] | None = None) -> None:
    """Open a database session, run the daily program workflow, and print JSON."""

    configure_logging()
    args = parse_args(argv)
    planned_date = parse_planned_date(args.planned_date)
    async with AsyncSessionLocal() as session:
        service = LivingForumService(session)
        if args.engage_only:
            result = await service.engage_day(
                planned_date=planned_date,
                limit=args.reply_limit,
                dry_run=not args.run,
            )
        else:
            result = await service.publish_day(
                planned_date=planned_date,
                limit=args.limit,
                publish_mode=args.publish_mode,
                dry_run=not args.run,
            )
            if args.engage:
                result = {
                    "publish": result,
                    "engagement": await service.engage_day(
                        planned_date=planned_date,
                        limit=args.reply_limit,
                        dry_run=not args.run,
                    ),
                }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def parse_planned_date(value: str | None) -> date | None:
    """Convert an optional ISO date argument into a `date` object."""

    return date.fromisoformat(value) if value else None


def main() -> None:
    """CLI entry point for local and scheduled manual program runs."""

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
