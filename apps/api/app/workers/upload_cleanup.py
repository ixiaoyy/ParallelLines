import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.services.uploads import UploadService


async def run_once() -> int:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        return await UploadService(session, settings).cleanup_expired_temporary_uploads()


async def run_forever() -> None:
    configure_logging()
    settings = get_settings()
    logger = get_logger("worker.upload_cleanup")
    logger.info("worker_started", interval_seconds=settings.upload_cleanup_interval_seconds)

    while True:
        try:
            deleted_count = await run_once()
            logger.info("expired_uploads_cleaned", deleted_count=deleted_count)
        except Exception as exc:
            logger.exception("upload_cleanup_failed", error=str(exc))
        await asyncio.sleep(settings.upload_cleanup_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
