"""Trade management: breakeven, trailing, partial booking, time-stop."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.execution import ExecutionService
from app.models import BrokerAccount, Position

logger = logging.getLogger(__name__)


class TradeManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.execution = ExecutionService(db)

    async def manage_open_positions(self, ltp_map: dict[str, float]) -> None:
        result = await self.db.execute(select(Position))
        positions = result.scalars().all()
        for pos in positions:
            ltp = ltp_map.get(pos.symbol)
            if ltp is None:
                continue
            await self._check_exits(pos, ltp)

    async def _check_exits(self, pos: Position, ltp: float) -> None:
        account = (
            await self.db.execute(
                select(BrokerAccount).where(BrokerAccount.id == pos.broker_account_id)
            )
        ).scalar_one()

        sl = float(pos.stop_loss) if pos.stop_loss else None
        tgt = float(pos.target) if pos.target else None
        entry = float(pos.avg_price)

        if pos.side == "BUY":
            if sl and ltp <= sl:
                await self.execution.close_position(account, pos, ltp, "stop_loss", pos.paper)
                return
            if tgt and ltp >= tgt:
                await self.execution.close_position(account, pos, ltp, "target", pos.paper)
                return
            if ltp >= entry * 1.005 and sl and sl < entry:
                pos.stop_loss = Decimal(str(entry))
        else:
            if sl and ltp >= sl:
                await self.execution.close_position(account, pos, ltp, "stop_loss", pos.paper)
                return
            if tgt and ltp <= tgt:
                await self.execution.close_position(account, pos, ltp, "target", pos.paper)
                return
            if ltp <= entry * 0.995 and sl and sl > entry:
                pos.stop_loss = Decimal(str(entry))

    async def eod_square_off(self) -> None:
        result = await self.db.execute(select(Position))
        positions = result.scalars().all()
        for pos in positions:
            account = (
                await self.db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == pos.broker_account_id)
                )
            ).scalar_one()
            ltp = float(pos.avg_price)
            await self.execution.close_position(account, pos, ltp, "eod_squareoff", pos.paper)
        logger.info("EOD square-off completed for %d positions", len(positions))
