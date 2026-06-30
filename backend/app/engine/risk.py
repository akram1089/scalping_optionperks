"""Risk guards: daily max loss, max trades, consecutive loss pause, kill switch."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlobalState, RiskEvent, Strategy, Trade


@dataclass
class RiskStatus:
    ok: bool
    reason: str | None = None


class RiskGuard:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._consec_losses: dict[UUID, int] = {}
        self._paused: set[UUID] = set()

    async def check_global(self) -> RiskStatus:
        result = await self.db.execute(select(GlobalState).where(GlobalState.id == 1))
        gs = result.scalar_one_or_none()
        if gs and gs.kill_switch:
            return RiskStatus(ok=False, reason="kill_switch")
        return RiskStatus(ok=True)

    async def check_strategy(self, strategy: Strategy, account_id: UUID) -> RiskStatus:
        global_status = await self.check_global()
        if not global_status.ok:
            return global_status

        if strategy.id in self._paused:
            return RiskStatus(ok=False, reason="consec_pause")

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        trades_today = (
            await self.db.execute(
                select(func.count(Trade.id)).where(
                    Trade.strategy_id == strategy.id,
                    Trade.broker_account_id == account_id,
                    Trade.opened_at >= today_start,
                )
            )
        ).scalar() or 0

        if trades_today >= strategy.max_trades_day:
            return RiskStatus(ok=False, reason="max_trades")

        pnl_today = (
            await self.db.execute(
                select(func.coalesce(func.sum(Trade.pnl), 0)).where(
                    Trade.strategy_id == strategy.id,
                    Trade.broker_account_id == account_id,
                    Trade.opened_at >= today_start,
                    Trade.closed_at.isnot(None),
                )
            )
        ).scalar() or Decimal(0)

        if pnl_today <= -abs(strategy.daily_max_loss):
            await self._log_event(strategy.id, account_id, "max_loss", f"Daily loss {pnl_today}")
            return RiskStatus(ok=False, reason="max_loss")

        consec = self._consec_losses.get(strategy.id, 0)
        if consec >= strategy.consec_loss_limit:
            self._paused.add(strategy.id)
            await self._log_event(
                strategy.id, account_id, "consec_pause", f"{consec} consecutive losses"
            )
            return RiskStatus(ok=False, reason="consec_pause")

        return RiskStatus(ok=True)

    def record_trade_result(self, strategy_id: UUID, pnl: Decimal) -> None:
        if pnl < 0:
            self._consec_losses[strategy_id] = self._consec_losses.get(strategy_id, 0) + 1
        else:
            self._consec_losses[strategy_id] = 0
            self._paused.discard(strategy_id)

    async def _log_event(
        self, strategy_id: UUID, account_id: UUID, event_type: str, detail: str
    ) -> None:
        self.db.add(
            RiskEvent(
                strategy_id=strategy_id,
                broker_account_id=account_id,
                event_type=event_type,
                detail=detail,
            )
        )
