from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.services.daily_reading import DailyReadingService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI controls for previewing or publishing one local reading day."""

    parser = argparse.ArgumentParser(
        description="Preview or publish two persona-written reading reflections for one day."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Publish through the canonical forum path; preview is the default.",
    )
    parser.add_argument(
        "--date",
        dest="planned_date",
        help="Asia/Shanghai date in YYYY-MM-DD format; defaults to today.",
    )
    parser.add_argument(
        "--force-local",
        action="store_true",
        help="Use the deterministic local content provider even when AI is configured.",
    )
    parser.add_argument(
        "--slot",
        type=int,
        choices=(1, 2),
        action="append",
        help="Preview or publish only one slot; repeat to select both. Defaults to both.",
    )
    parser.add_argument(
        "--publish-mode",
        choices=("auto", "preview", "off"),
        default=None,
        help="Override DAILY_READING_PUBLISH_MODE for this invocation.",
    )
    return parser.parse_args(argv)


async def async_main(argv: Sequence[str] | None = None) -> None:
    """Run one preview or publish flow and print a JSON summary.

    Key parameter is optional raw CLI arguments for tests. Return value is none.
    Side effect: opens an API database session and may publish two topics only
    when `--run` is supplied and the effective mode is `auto`.
    """

    configure_logging()
    args = parse_args(argv)
    planned_date = date.fromisoformat(args.planned_date) if args.planned_date else None
    async with AsyncSessionLocal() as session:
        result = await DailyReadingService(session).publish_day(
            planned_date,
            publish_mode=args.publish_mode,
            dry_run=not args.run,
            force_local=args.force_local,
            slots=args.slot,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    """Start the asynchronous daily-reading CLI and return no value."""

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
