"""REST LTP polling for brokers without KiteTicker (e.g. Zerodha enctoken)."""

import asyncio
import logging
from typing import Any

from app.broker.factory import get_broker_for_account
from app.broker.index_symbols import INDEX_LTP_ALIASES
from app.broker.ltp_fetch import fetch_all_index_ltp
from app.broker.ticker import RedisPubSub, publish_tick_threadsafe
from app.models import BrokerAccount

logger = logging.getLogger(__name__)


class LtpPoller:
    """Poll quote/LTP endpoints and publish ticks to Redis."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._broker: Any = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, account: BrokerAccount) -> None:
        await self.stop()
        self._broker = get_broker_for_account(account)
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("LTP poller started (%d indices)", len(INDEX_LTP_ALIASES))

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
        if not self._broker:
            return
        loop = asyncio.get_running_loop()
        quotes = await fetch_all_index_ltp(self._broker, loop)
        for display, q in quotes.items():
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
            if publish_tick_threadsafe:
                publish_tick_threadsafe(display, payload)
            else:
                await RedisPubSub.publish_tick(display, payload)


ltp_poller = LtpPoller()
