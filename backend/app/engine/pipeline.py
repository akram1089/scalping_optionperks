"""Aladin signal pipeline — full decision flow."""

import logging
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.broker.session import account_session_active, get_broker_for_account
from app.config import get_settings
from app.engine.fleet import fan_out_signal
from app.engine.indicators import IndicatorParams, compute_atr, snapshot_at
from app.engine.risk import RiskGuard
from app.engine.sizing import calculate_qty, stop_from_atr, target_from_rr
from app.models import BrokerAccount, Signal, Strategy, StrategyAccount

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class SignalPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk = RiskGuard(db)
        self.settings = get_settings()

    async def run_cycle(self, strategy: Strategy) -> dict | None:
        if not strategy.running:
            return None

        global_status = await self.risk.check_global()
        if not global_status.ok:
            return {"skipped": global_status.reason}

        if not self._market_open():
            return {"skipped": "market_closed"}

        if self._in_avoid_window(strategy):
            return {"skipped": "avoid_window"}

        candles = await self._fetch_candles(strategy)
        if candles is None or len(candles) < 30:
            return {"skipped": "insufficient_data"}

        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])

        params = IndicatorParams(**(strategy.params_json or {}))
        snap = snapshot_at(closes, params)
        if not snap:
            return {"skipped": "no_indicator"}

        atr = compute_atr(highs, lows, closes)
        atr_band = strategy.atr_band_json or {}
        min_atr = atr_band.get("min_atr", 0.5)
        max_atr = atr_band.get("max_atr", 5.0)
        if atr < min_atr or atr > max_atr:
            return {"skipped": "atr_out_of_band"}

        side = None
        if snap.long_bias:
            side = "BUY"
        elif snap.short_bias:
            side = "SELL"
        if not side:
            return {"skipped": "no_signal"}

        htf_ok = await self._htf_confirms(strategy, side)
        if not htf_ok:
            return {"skipped": "htf_mismatch"}

        price = float(closes[-1])
        stop = stop_from_atr(price, atr, side)
        target = target_from_rr(price, stop, side, float(strategy.rr_ratio))

        accounts = await self._get_accounts(strategy)
        if not accounts:
            return {"skipped": "no_accounts"}

        for acc in accounts:
            risk_status = await self.risk.check_strategy(strategy, acc.id)
            if not risk_status.ok:
                return {"skipped": risk_status.reason}

        signal = Signal(
            strategy_id=strategy.id,
            side=side,
            tf=strategy.entry_tf,
            price=Decimal(str(price)),
            indicator_snapshot_json={
                "rsi": snap.rsi,
                "aladin_signal": snap.aladin_signal,
                "aladin_fast": snap.aladin_fast,
                "atr": atr,
            },
            paper=strategy.paper_mode,
        )
        self.db.add(signal)
        await self.db.flush()

        qty_map = {}
        for acc in accounts:
            qty = calculate_qty(acc.capital, strategy.risk_pct, price, stop, lot_size=1)
            qty_map[acc.id] = qty

        if strategy.paper_mode:
            signal.acted = True
            logger.info(
                "PAPER signal %s %s @ %s qty_map=%s",
                side,
                strategy.symbol,
                price,
                qty_map,
            )
            from app.broker.ticker import RedisPubSub

            await RedisPubSub.publish_tick(
                strategy.symbol,
                {
                    "signal": side,
                    "price": price,
                    "paper": True,
                    "strategy_id": str(strategy.id),
                },
            )
            return {
                "signal_id": str(signal.id),
                "side": side,
                "price": price,
                "paper": True,
                "qty_map": {str(k): v for k, v in qty_map.items()},
            }

        results = await fan_out_signal(
            self.db, strategy, side, strategy.symbol, qty_map, price, stop, target
        )
        signal.acted = any(r.get("status") == "ok" for r in results)
        return {
            "signal_id": str(signal.id),
            "side": side,
            "price": price,
            "paper": False,
            "results": results,
        }

    def _market_open(self) -> bool:
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return False
        market_open = time(9, 15)
        market_close = time(15, 30)
        return market_open <= now.time() <= market_close

    def _in_avoid_window(self, strategy: Strategy) -> bool:
        now = datetime.now(IST)
        open_avoid = (datetime.combine(now.date(), time(9, 15)) + timedelta(minutes=strategy.avoid_open_min)).time()
        close_avoid = (datetime.combine(now.date(), time(15, 30)) - timedelta(minutes=strategy.avoid_close_min)).time()
        t = now.time()
        if t < open_avoid or t > close_avoid:
            return True
        return False

    async def _fetch_candles(self, strategy: Strategy) -> list[dict] | None:
        account = await self._first_connected_account(strategy)
        if not account:
            return self._mock_candles()

        exchange = "NFO" if strategy.instrument_type in ("futures", "options") else "NSE"
        try:
            broker = get_broker_for_account(account)
            try:
                to_date = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                from_date = (datetime.now(IST) - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
                return broker.historical_data(
                    exchange, strategy.symbol, from_date, to_date, strategy.entry_tf
                )
            finally:
                broker.close()
        except Exception:
            logger.exception("Failed to fetch candles, using mock data")
            return self._mock_candles()

    def _mock_candles(self) -> list[dict]:
        """Synthetic candles for paper/dev mode without live Kite session."""
        base = 100.0
        candles = []
        for i in range(60):
            o = base + np.sin(i / 5) * 2
            c = o + np.random.uniform(-0.5, 0.5)
            h = max(o, c) + 0.3
            l = min(o, c) - 0.3
            candles.append({"open": o, "high": h, "low": l, "close": c, "volume": 1000})
            base = c
        return candles

    async def _htf_confirms(self, strategy: Strategy, side: str) -> bool:
        account = await self._first_connected_account(strategy)
        if not account:
            return True
        exchange = "NFO" if strategy.instrument_type in ("futures", "options") else "NSE"
        try:
            broker = get_broker_for_account(account)
            try:
                to_date = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                from_date = (datetime.now(IST) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
                htf_candles = broker.historical_data(
                    exchange, strategy.symbol, from_date, to_date, strategy.htf
                )
            finally:
                broker.close()
            closes = np.array([c["close"] for c in htf_candles])
            if len(closes) < 30:
                return True
            snap = snapshot_at(closes, IndicatorParams(**(strategy.params_json or {})))
            if not snap:
                return True
            if side == "BUY":
                return snap.aladin_fast > snap.aladin_signal
            return snap.aladin_fast < snap.aladin_signal
        except Exception:
            return True

    async def _get_accounts(self, strategy: Strategy) -> list[BrokerAccount]:
        result = await self.db.execute(
            select(BrokerAccount)
            .join(StrategyAccount)
            .where(
                StrategyAccount.strategy_id == strategy.id,
                StrategyAccount.enabled.is_(True),
                BrokerAccount.enabled.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _first_connected_account(self, strategy: Strategy) -> BrokerAccount | None:
        accounts = await self._get_accounts(strategy)
        today = datetime.now(IST).date()
        for acc in accounts:
            if account_session_active(acc):
                return acc
        return accounts[0] if accounts else None
