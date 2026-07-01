import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

TICK_CHANNEL = "scalpdesk:ticks"
TICK_CACHE_PREFIX = "tick:"

_event_loop: asyncio.AbstractEventLoop | None = None


def set_tick_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _event_loop
    _event_loop = loop


def publish_tick_threadsafe(symbol: str, data: dict) -> None:
    if _event_loop is None or _event_loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(
        RedisPubSub.publish_tick(symbol, data), _event_loop
    )


class RedisPubSub:
    _client: aioredis.Redis | None = None

    @classmethod
    async def get_client(cls) -> aioredis.Redis:
        if cls._client is None:
            settings = get_settings()
            cls._client = aioredis.from_url(settings.redis_url, decode_responses=True)
        return cls._client

    @classmethod
    async def publish_tick(cls, symbol: str, data: dict[str, Any]) -> None:
        client = await cls.get_client()
        payload = json.dumps({"symbol": symbol, "ts": time.time(), **data})
        await client.set(f"{TICK_CACHE_PREFIX}{symbol}", payload, ex=120)
        await client.publish(TICK_CHANNEL, payload)

    @classmethod
    async def publish_instrument_tick(
        cls, symbol: str, instrument_token: int, data: dict[str, Any]
    ) -> None:
        body = {**data, "instrument_token": instrument_token, "symbol": symbol}
        await cls.publish_tick(symbol, body)
        await cls.publish_tick(f"token:{instrument_token}", body)

    @classmethod
    async def get_tick(cls, symbol: str) -> dict[str, Any] | None:
        client = await cls.get_client()
        raw = await client.get(f"{TICK_CACHE_PREFIX}{symbol}")
        return json.loads(raw) if raw else None

    @classmethod
    async def subscribe(cls):
        client = await cls.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(TICK_CHANNEL)
        return pubsub


class TickerManager:
    """Manages Kite Ticker WebSocket — indices + dynamically subscribed chart symbols."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._tokens: list[int] = []
        self._symbol_map: dict[int, str] = {}
        self._publish: Callable[[str, dict[str, Any]], None] | None = None
        self._ws: Any = None
        self._lock = threading.Lock()
        self._api_key = ""
        self._access_token = ""

    def set_instruments(self, token_symbol_map: dict[int, str]) -> None:
        with self._lock:
            self._symbol_map = dict(token_symbol_map)
            self._tokens = list(self._symbol_map.keys())

    def merge_subscriptions(self, token_symbol_map: dict[int, str]) -> list[int]:
        """Add instrument tokens; returns newly added token ids."""
        added: list[int] = []
        with self._lock:
            for token, sym in token_symbol_map.items():
                if token not in self._symbol_map:
                    added.append(token)
                self._symbol_map[token] = sym
            self._tokens = list(self._symbol_map.keys())
            ws = self._ws
        if ws and added:
            try:
                ws.subscribe(added)
                ws.set_mode(ws.MODE_QUOTE, added)
                logger.info("Kite ticker subscribed +%d tokens (total %d)", len(added), len(self._tokens))
            except Exception:
                logger.exception("Kite ticker subscribe failed")
        return added

    def subscription_count(self) -> int:
        with self._lock:
            return len(self._symbol_map)

    def set_publish_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._publish = callback

    async def start(self, access_token: str, api_key: str) -> None:
        self._api_key = api_key
        self._access_token = access_token
        if self._running and self._ws is not None:
            return
        if self._running:
            await self.stop()
        self._running = True
        self._task = asyncio.create_task(self._run_ticker(api_key, access_token))

    @property
    def is_running(self) -> bool:
        return self._running

    async def stop(self) -> None:
        self._running = False
        with self._lock:
            self._ws = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_ticker(self, api_key: str, access_token: str) -> None:
        try:
            from kiteconnect import KiteTicker

            kws = KiteTicker(api_key, access_token)
            publish = self._publish

            def on_ticks(ws, ticks):
                for tick in ticks:
                    token = tick.get("instrument_token")
                    if token is None:
                        continue
                    with self._lock:
                        symbol = self._symbol_map.get(token, str(token))
                    ltp = tick.get("last_price", 0)
                    ohlc = tick.get("ohlc") or {}
                    prev = ohlc.get("close") or 0
                    change = tick.get("change")
                    if change is None and prev and ltp:
                        change = ((ltp - prev) / prev) * 100
                    payload = {
                        "instrument_token": token,
                        "ltp": ltp,
                        "change_pct": change or 0,
                        "volume": tick.get("volume_traded", 0),
                        "ohlc": ohlc,
                    }
                    if _event_loop and not _event_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            RedisPubSub.publish_instrument_tick(symbol, int(token), payload),
                            _event_loop,
                        )
                    elif publish:
                        publish(symbol, payload)

            def on_connect(ws, response):
                with self._lock:
                    self._ws = ws
                    tokens = list(self._tokens)
                if tokens:
                    ws.subscribe(tokens)
                    ws.set_mode(ws.MODE_QUOTE, tokens)
                logger.info("Kite ticker connected, subscribed to %d tokens", len(tokens))

            def on_error(ws, code, reason):
                logger.error("Kite ticker error code=%s reason=%s", code, reason)

            def on_close(ws, code, reason):
                logger.warning("Kite ticker closed code=%s reason=%s — reconnecting", code, reason)
                with self._lock:
                    self._ws = None

            kws.on_ticks = on_ticks
            kws.on_connect = on_connect
            kws.on_error = on_error
            kws.on_close = on_close
            kws.connect(threaded=True)

            while self._running:
                await asyncio.sleep(1)
        except Exception:
            logger.exception("Ticker error")
            self._running = False


ticker_manager = TickerManager()
