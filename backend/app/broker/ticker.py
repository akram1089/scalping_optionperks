import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

TICK_CHANNEL = "scalpdesk:ticks"
TICK_CACHE_PREFIX = "tick:"


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
        payload = json.dumps({"symbol": symbol, **data})
        await client.set(f"{TICK_CACHE_PREFIX}{symbol}", payload, ex=60)
        await client.publish(TICK_CHANNEL, payload)

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
    """Manages Kite Ticker WebSocket connections per account."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._tokens: list[int] = []
        self._symbol_map: dict[int, str] = {}

    def set_instruments(self, token_symbol_map: dict[int, str]) -> None:
        self._symbol_map = token_symbol_map
        self._tokens = list(token_symbol_map.keys())

    async def start(self, access_token: str, api_key: str) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_ticker(api_key, access_token))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_ticker(self, api_key: str, access_token: str) -> None:
        try:
            from kiteconnect import KiteTicker

            kws = KiteTicker(api_key, access_token)

            def on_ticks(ws, ticks):
                for tick in ticks:
                    token = tick.get("instrument_token")
                    symbol = self._symbol_map.get(token, str(token))
                    ltp = tick.get("last_price", 0)
                    change = tick.get("change", 0)
                    asyncio.get_event_loop().create_task(
                        RedisPubSub.publish_tick(
                            symbol,
                            {
                                "ltp": ltp,
                                "change_pct": change,
                                "volume": tick.get("volume_traded", 0),
                                "ohlc": tick.get("ohlc", {}),
                            },
                        )
                    )

            def on_connect(ws, response):
                if self._tokens:
                    ws.subscribe(self._tokens)
                    ws.set_mode(ws.MODE_LTP, self._tokens)

            kws.on_ticks = on_ticks
            kws.on_connect = on_connect
            kws.connect(threaded=True)

            while self._running:
                await asyncio.sleep(1)
        except Exception:
            logger.exception("Ticker error")
            self._running = False


ticker_manager = TickerManager()
