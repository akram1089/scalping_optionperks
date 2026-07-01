"""Start Kite live ticker when a Zerodha session is available."""

import asyncio
import logging

from sqlalchemy import select

from app.auth.crypto import decrypt_value
from app.broker.factory import account_session_active
from app.broker.ticker import RedisPubSub, ticker_manager
from app.db import async_session
from app.models import BrokerAccount, Instrument

logger = logging.getLogger(__name__)

# Dashboard IndexCard labels → instrument tradingsymbol(s) to resolve
_INDEX_TARGETS: list[tuple[str, str, str]] = [
    ("NIFTY 50", "NSE", "NIFTY 50"),
    ("NIFTY 50", "NSE", "NIFTY"),
    ("BANK NIFTY", "NSE", "BANKNIFTY"),
    ("SENSEX", "BSE", "SENSEX"),
]

_event_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _event_loop
    _event_loop = loop


def publish_tick_threadsafe(symbol: str, data: dict) -> None:
    if _event_loop is None or _event_loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(RedisPubSub.publish_tick(symbol, data), _event_loop)


async def bootstrap_live_ticker() -> bool:
    """Connect KiteTicker for index LTP if any Zerodha account has an active session."""
    set_event_loop(asyncio.get_running_loop())

    async with async_session() as db:
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.broker == "zerodha",
                BrokerAccount.enabled.is_(True),
            )
        )
        accounts = list(result.scalars().all())
        account = next((a for a in accounts if account_session_active(a)), None)
        if not account:
            logger.info("Live ticker: no connected Zerodha account")
            return False

        api_key = decrypt_value(account.api_key_enc) if account.api_key_enc else ""
        if account.auth_mode == "enctoken":
            session_token = (
                decrypt_value(account.enctoken_enc) if account.enctoken_enc else ""
            )
        else:
            session_token = (
                decrypt_value(account.access_token_enc) if account.access_token_enc else ""
            )

        if not api_key or not session_token:
            logger.warning(
                "Live ticker: Zerodha account %s missing api_key or session token",
                account.label,
            )
            return False

        token_map: dict[int, str] = {}
        seen_labels: set[str] = set()

        for display, exchange, tradingsymbol in _INDEX_TARGETS:
            if display in seen_labels:
                continue
            inst = await db.execute(
                select(Instrument).where(
                    Instrument.exchange == exchange,
                    Instrument.tradingsymbol == tradingsymbol,
                    Instrument.is_active.is_(True),
                )
            )
            row = inst.scalar_one_or_none()
            if row and row.instrument_token not in token_map:
                token_map[row.instrument_token] = display
                seen_labels.add(display)

        if not token_map:
            logger.warning("Live ticker: no index instruments in DB — run instrument sync")
            return False

        await ticker_manager.stop()
        ticker_manager.set_instruments(token_map)
        ticker_manager.set_publish_callback(publish_tick_threadsafe)
        await ticker_manager.start(session_token, api_key)
        logger.info(
            "Live ticker started for %s (%d indices)",
            account.label,
            len(token_map),
        )
        return True
