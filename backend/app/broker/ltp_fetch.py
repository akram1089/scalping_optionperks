"""Fetch index LTP — REST for OAuth, historical fallback for enctoken."""

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.broker.index_symbols import INDEX_LTP_ALIASES

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def fetch_index_ltp_sync(broker: Any, display: str, aliases: list[str]) -> dict[str, Any] | None:
    """OAuth only — enctoken REST quote/ltp is blocked by Zerodha (400)."""
    for key in aliases:
        for method_name in ("ltp", "quote"):
            try:
                method = getattr(broker, method_name, None)
                if method is None:
                    continue
                quotes = method([key])
                q = quotes.get(key) or {}
                ltp = q.get("last_price") or q.get("ltp")
                if ltp is not None:
                    return q
            except Exception as exc:
                logger.debug("Index LTP %s via %s failed for %s: %s", key, method_name, display, exc)
    return None


def fetch_index_ltp_historical_sync(
    inner: Any, token: int, display: str
) -> dict[str, Any] | None:
    """Last 5m candle close as LTP proxy (works with enctoken OMS historical API)."""
    now = datetime.now(IST)
    from_dt = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    to_dt = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        candles = inner.historical_data(token, from_dt, to_dt, "5minute")
        if not candles:
            return None
        close = candles[-1].get("close")
        if close is None:
            return None
        return {"last_price": close, "ohlc": {"close": close}, "volume": 0}
    except Exception as exc:
        logger.debug("Historical LTP fallback failed for %s token %s: %s", display, token, exc)
        return None


async def fetch_all_index_ltp_oauth(broker: Any, loop) -> dict[str, dict[str, Any]]:
    """REST quote fetch for Kite Connect OAuth sessions."""
    result: dict[str, dict[str, Any]] = {}
    for display, aliases in INDEX_LTP_ALIASES.items():
        q = await loop.run_in_executor(
            None, lambda d=display, a=aliases: fetch_index_ltp_sync(broker, d, a)
        )
        if q:
            result[display] = q
    return result


async def fetch_all_index_ltp_historical(
    inner: Any, token_map: dict[int, str], loop
) -> dict[str, dict[str, Any]]:
    """Historical candle fallback when WebSocket ticks not yet in Redis."""
    result: dict[str, dict[str, Any]] = {}
    for token, display in token_map.items():
        q = await loop.run_in_executor(
            None, lambda t=token, d=display: fetch_index_ltp_historical_sync(inner, t, d)
        )
        if q:
            result[display] = q
    return result
