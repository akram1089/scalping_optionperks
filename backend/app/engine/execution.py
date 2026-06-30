"""Order execution: bracket orders, fill handling, paper mode."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import decrypt_value
from app.broker.session import get_broker_for_account
from app.models import BrokerAccount, Order, Position, Trade

logger = logging.getLogger(__name__)


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
            order.kite_order_id = f"PAPER-{uuid.uuid4().hex[:8]}"
            await self._open_position(account, strategy_id, symbol, side, qty, price, stop_loss, target, paper)
        else:
            try:
                kite = await self._kite_for_account(account)
                txn_type = kite.kite.TRANSACTION_TYPE_BUY if side == "BUY" else kite.kite.TRANSACTION_TYPE_SELL
                oid = kite.place_order(
                    variety=kite.kite.VARIETY_REGULAR,
                    exchange="NSE",
                    tradingsymbol=symbol,
                    transaction_type=txn_type,
                    quantity=qty,
                    product=kite.kite.PRODUCT_MIS,
                    order_type=kite.kite.ORDER_TYPE_LIMIT,
                    price=price,
                )
                order.kite_order_id = str(oid)
                order.status = "OPEN"
                await self._open_position(account, strategy_id, symbol, side, qty, price, stop_loss, target, paper)
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
        side_exit = "SELL" if position.side == "BUY" else "BUY"
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
            kite_order_id=f"PAPER-{uuid.uuid4().hex[:8]}" if paper else None,
        )
        self.db.add(order)
        await self.db.flush()

        if not paper:
            kite = await self._kite_for_account(account)
            txn = (
                kite.kite.TRANSACTION_TYPE_SELL
                if position.side == "BUY"
                else kite.kite.TRANSACTION_TYPE_BUY
            )
            kite.place_order(
                variety=kite.kite.VARIETY_REGULAR,
                exchange="NSE",
                tradingsymbol=position.symbol,
                transaction_type=txn,
                quantity=position.qty,
                product=kite.kite.PRODUCT_MIS,
                order_type=kite.kite.ORDER_TYPE_MARKET,
            )

        entry = float(position.avg_price)
        pnl = (exit_price - entry) * position.qty
        if position.side == "SELL":
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

    async def _kite_for_account(self, account: BrokerAccount):
        return get_broker_for_account(account)
