"""Fetch index LTP using canonical Zerodha quote keys."""

import logging
from typing import Any

from app.broker.index_symbols import INDEX_LTP_ALIASES

logger = logging.getLogger(__name__)


def fetch_index_ltp_sync(broker: Any, display: str, aliases: list[str]) -> dict[str, Any] | None:
    """Try each exchange:symbol alias; use /quote as fallback to /quote/ltp."""
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


async def fetch_all_index_ltp(broker: Any, loop) -> dict[str, dict[str, Any]]:
    """Fetch all dashboard indices; returns display label → quote payload."""
    result: dict[str, dict[str, Any]] = {}
    for display, aliases in INDEX_LTP_ALIASES.items():
        q = await loop.run_in_executor(
            None, lambda d=display, a=aliases: fetch_index_ltp_sync(broker, d, a)
        )
        if q:
            result[display] = q
    return result
