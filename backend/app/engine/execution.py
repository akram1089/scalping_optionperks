"""Order execution: bracket orders, fill handling, paper mode."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY, SIDE_SELL
from app.broker.session import get_broker_for_account
from app.models import BrokerAccount, Order, Position, Trade

logger = logging.getLogger(__name__)


def _exchange_for_symbol(symbol: str) -> str:
    """Infer exchange from tradingsymbol — NFO contracts contain expiry month codes."""
    if any(x in symbol for x in ("FUT", "CE", "PE")) or symbol.startswith("NIFTY"):
        return "NFO"
    return "NSE"


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def place_entry(
        self,
        account: BrokerAccount,
        strategy_id: UUID,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        stop_loss: float,
        target: float,
        paper: bool,
    ) -> Order:
        order = Order(
            broker_account_id=account.id,
            strategy_id=strategy_id,
            side=side,
            symbol=symbol,
            qty=qty,
            price=Decimal(str(price)),
            order_type="LIMIT",
            status="PENDING",
            paper=paper,
        )
        self.db.add(order)
        await self.db.flush()

        if paper:
            order.status = "COMPLETE"
            order.broker_order_id = f"PAPER-{uuid.uuid4().hex[:8]}"
            await self._open_position(account, strategy_id, symbol, side, qty, price, stop_loss, target, paper)
        else:
            try:
                broker = get_broker_for_account(account)
                try:
                    exchange = _exchange_for_symbol(symbol)
                    oid = broker.place_order(
                        exchange=exchange,
                        symbol=symbol,
                        side=side,
                        qty=qty,
                        product=PRODUCT_MIS,
                        order_type=ORDER_LIMIT,
                        price=price,
                    )
                    order.broker_order_id = str(oid)
                    order.status = "OPEN"
                    await self._open_position(
                        account, strategy_id, symbol, side, qty, price, stop_loss, target, paper
                    )
                finally:
                    broker.close()
            except Exception as exc:
                logger.exception("Order placement failed")
                order.status = "REJECTED"
                order.raw_json = {"error": str(exc)}
                raise

        return order

    async def _open_position(
        self,
        account: BrokerAccount,
        strategy_id: UUID,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        stop_loss: float,
        target: float,
        paper: bool,
    ) -> None:
        pos = Position(
            broker_account_id=account.id,
            strategy_id=strategy_id,
            symbol=symbol,
            qty=qty,
            avg_price=Decimal(str(price)),
            side=side,
            stop_loss=Decimal(str(stop_loss)),
            target=Decimal(str(target)),
            paper=paper,
        )
        self.db.add(pos)

    async def close_position(
        self,
        account: BrokerAccount,
        position: Position,
        exit_price: float,
        exit_reason: str,
        paper: bool,
    ) -> Trade:
        side_exit = SIDE_SELL if position.side == SIDE_BUY else SIDE_BUY
        order = Order(
            broker_account_id=account.id,
            strategy_id=position.strategy_id,
            side=side_exit,
            symbol=position.symbol,
            qty=position.qty,
            price=Decimal(str(exit_price)),
            order_type="MARKET",
            status="COMPLETE" if paper else "PENDING",
            paper=paper,
            broker_order_id=f"PAPER-{uuid.uuid4().hex[:8]}" if paper else None,
        )
        self.db.add(order)
        await self.db.flush()

        if not paper:
            broker = get_broker_for_account(account)
            try:
                exchange = _exchange_for_symbol(position.symbol)
                broker.place_order(
                    exchange=exchange,
                    symbol=position.symbol,
                    side=side_exit,
                    qty=position.qty,
                    product=PRODUCT_MIS,
                    order_type=ORDER_MARKET,
                )
            finally:
                broker.close()

        entry = float(position.avg_price)
        pnl = (exit_price - entry) * position.qty
        if position.side == SIDE_SELL:
            pnl = -pnl

        trade = Trade(
            broker_account_id=account.id,
            strategy_id=position.strategy_id,
            entry_order_id=None,
            exit_order_id=order.id,
            side=position.side,
            symbol=position.symbol,
            qty=position.qty,
            entry_price=position.avg_price,
            exit_price=Decimal(str(exit_price)),
            pnl=Decimal(str(round(pnl, 2))),
            exit_reason=exit_reason,
            closed_at=datetime.now(UTC),
            paper=paper,
        )
        self.db.add(trade)
        await self.db.delete(position)
        return trade
