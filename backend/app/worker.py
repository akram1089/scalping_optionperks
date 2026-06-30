"""Worker process: scheduler + strategy engine."""

import asyncio
import logging

from app.scheduler import ensure_global_state, resume_running_strategies, setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("ScalpDesk worker starting")
    await ensure_global_state()
    scheduler = setup_scheduler()
    scheduler.start()
    await resume_running_strategies()
    logger.info("Worker ready — scheduler running")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
