"""Runtime manager for active strategy loops."""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.db import async_session
from app.engine.pipeline import SignalPipeline
from app.models import Strategy

logger = logging.getLogger(__name__)


class StrategyRuntime:
    def __init__(self):
        self._tasks: dict[UUID, asyncio.Task] = {}
        self._running = False

    async def start_strategy(self, strategy_id: UUID) -> None:
        if strategy_id in self._tasks and not self._tasks[strategy_id].done():
            return
        self._tasks[strategy_id] = asyncio.create_task(self._loop(strategy_id))
        logger.info("Started strategy loop %s", strategy_id)

    async def stop_strategy(self, strategy_id: UUID) -> None:
        task = self._tasks.pop(strategy_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped strategy loop %s", strategy_id)

    async def stop_all(self) -> None:
        for sid in list(self._tasks.keys()):
            await self.stop_strategy(sid)

    async def _loop(self, strategy_id: UUID) -> None:
        while True:
            try:
                async with async_session() as db:
                    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
                    strategy = result.scalar_one_or_none()
                    if not strategy or not strategy.running:
                        break
                    pipeline = SignalPipeline(db)
                    outcome = await pipeline.run_cycle(strategy)
                    if outcome and outcome.get("side"):
                        logger.info("Pipeline outcome: %s", outcome)
                    await db.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Strategy loop error %s", strategy_id)
            await asyncio.sleep(60)


strategy_runtime = StrategyRuntime()
