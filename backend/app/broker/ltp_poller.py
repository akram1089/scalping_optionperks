"""REST LTP polling for brokers without KiteTicker (e.g. Zerodha enctoken)."""

import asyncio
import logging
from typing import Any

from app.broker.factory import get_broker_for_account
from app.broker.ticker import RedisPubSub, publish_tick_threadsafe
from app.models import BrokerAccount

logger = logging.getLogger(__name__)


class LtpPoller:
    """Poll quote/LTP endpoints and publish ticks to Redis."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._quote_keys: dict[str, str] = {}
        self._broker: Any = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_targets(self, quote_keys: dict[str, str]) -> None:
        """Map ``EXCHANGE:SYMBOL`` → dashboard display label."""
        self._quote_keys = quote_keys

    async def start(self, account: BrokerAccount) -> None:
        await self.stop()
        self._broker = get_broker_for_account(account)
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("LTP poller started (%d symbols)", len(self._quote_keys))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._broker is not None:
            try:
                self._broker.close()
            except Exception:
                pass
            self._broker = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("LTP poll error")
            await asyncio.sleep(2)

    async def _poll_once(self) -> None:
        if not self._broker or not self._quote_keys:
            return
        keys = list(self._quote_keys.keys())
        loop = asyncio.get_running_loop()
        quotes = await loop.run_in_executor(None, lambda: self._broker.ltp(keys))
        for quote_key, display in self._quote_keys.items():
            q = quotes.get(quote_key) or {}
            ltp = q.get("last_price") or q.get("ltp")
            if ltp is None:
                continue
            ohlc = q.get("ohlc") or {}
            prev = ohlc.get("close") or 0
            change_pct = ((ltp - prev) / prev * 100) if prev else 0
            payload = {
                "ltp": ltp,
                "change_pct": change_pct,
                "volume": q.get("volume", 0),
                "ohlc": ohlc,
            }
            publish = publish_tick_threadsafe
            if publish:
                publish(display, payload)
            else:
                await RedisPubSub.publish_tick(display, payload)


ltp_poller = LtpPoller()
