"""Multi-account fan-out with isolated failure handling."""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.execution import ExecutionService
from app.models import BrokerAccount, RiskEvent, Strategy, StrategyAccount

logger = logging.getLogger(__name__)


async def fan_out_signal(
    db: AsyncSession,
    strategy: Strategy,
    side: str,
    symbol: str,
    qty_map: dict[UUID, int],
    price: float,
    stop_loss: float,
    target: float,
) -> list[dict]:
    """Execute signal across all enabled accounts. Failures are isolated."""
    result = await db.execute(
        select(StrategyAccount, BrokerAccount)
        .join(BrokerAccount, StrategyAccount.broker_account_id == BrokerAccount.id)
        .where(
            StrategyAccount.strategy_id == strategy.id,
            StrategyAccount.enabled.is_(True),
            BrokerAccount.enabled.is_(True),
        )
    )
    rows = result.all()
    execution = ExecutionService(db)
    results = []

    async def _execute_one(sa: StrategyAccount, account: BrokerAccount) -> dict:
        qty = qty_map.get(account.id, 0)
        if qty <= 0:
            return {"account_id": str(account.id), "status": "skipped", "reason": "zero_qty"}
        try:
            order = await execution.place_entry(
                account=account,
                strategy_id=strategy.id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                stop_loss=stop_loss,
                target=target,
                paper=strategy.paper_mode,
            )
            return {
                "account_id": str(account.id),
                "status": "ok",
                "order_id": str(order.id),
            }
        except Exception as exc:
            logger.exception("Fan-out failed for account %s", account.id)
            db.add(
                RiskEvent(
                    broker_account_id=account.id,
                    strategy_id=strategy.id,
                    event_type="order_reject",
                    detail=str(exc),
                )
            )
            return {"account_id": str(account.id), "status": "error", "error": str(exc)}

    tasks = [_execute_one(sa, acc) for sa, acc in rows]
    if tasks:
        results = await asyncio.gather(*tasks)
    return list(results)


async def flatten_all_positions(db: AsyncSession, user_id: UUID, paper_only: bool = False) -> None:
    from app.engine.manage import TradeManager
    from app.models import Position

    result = await db.execute(
        select(Position)
        .join(BrokerAccount)
        .where(BrokerAccount.user_id == user_id)
    )
    positions = result.scalars().all()
    manager = TradeManager(db)
    execution = ExecutionService(db)
    for pos in positions:
        if paper_only and not pos.paper:
            continue
        account = (
            await db.execute(select(BrokerAccount).where(BrokerAccount.id == pos.broker_account_id))
        ).scalar_one()
        await execution.close_position(
            account, pos, float(pos.avg_price), "kill_switch", pos.paper
        )
