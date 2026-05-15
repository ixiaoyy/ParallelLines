import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.models.forum import Topic
from app.services.forum import calculate_hot_score


async def recompute_hot_scores(session: AsyncSession) -> int:
    """Recompute deterministic hot scores for all non-deleted topics."""

    topics = list(await session.scalars(select(Topic).where(Topic.deleted_at.is_(None))))
    for topic in topics:
        topic.hot_score = calculate_hot_score(
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            view_count=topic.view_count,
        )
    await session.commit()
    return len(topics)


async def run_once() -> int:
    async with AsyncSessionLocal() as session:
        return await recompute_hot_scores(session)


async def run_forever() -> None:
    configure_logging()
    settings = get_settings()
    logger = get_logger("worker.hot_ranking")
    logger.info("worker_started", interval_seconds=settings.hot_rank_interval_seconds)

    while True:
        try:
            updated_count = await run_once()
            logger.info("hot_scores_recomputed", updated_count=updated_count)
        except Exception as exc:
            logger.exception("hot_score_recompute_failed", error=str(exc))
        await asyncio.sleep(settings.hot_rank_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
