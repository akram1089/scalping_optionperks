"""Start live index LTP when a Zerodha session is available."""

import asyncio
import logging

from sqlalchemy import select

from app.auth.crypto import decrypt_value
from app.broker.factory import account_session_active
from app.broker.ltp_poller import ltp_poller
from app.broker.ticker import publish_tick_threadsafe, set_tick_event_loop, ticker_manager
from app.db import async_session
from app.models import BrokerAccount, Instrument

logger = logging.getLogger(__name__)

INDEX_DISPLAY_SYMBOLS = ("NIFTY 50", "BANK NIFTY", "SENSEX")

# Dashboard IndexCard labels → instrument tradingsymbol(s) to resolve
_INDEX_TARGETS: list[tuple[str, str, str]] = [
    ("NIFTY 50", "NSE", "NIFTY 50"),
    ("NIFTY 50", "NSE", "NIFTY"),
    ("BANK NIFTY", "NSE", "BANKNIFTY"),
    ("SENSEX", "BSE", "SENSEX"),
]

async def _resolve_index_maps(
    db,
) -> tuple[dict[str, str], dict[int, str]]:
    """Return (quote_key→display, token→display) for index instruments."""
    quote_keys: dict[str, str] = {}
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
        if not row:
            continue
        quote_key = f"{row.exchange}:{row.tradingsymbol}"
        if quote_key not in quote_keys:
            quote_keys[quote_key] = display
        if row.instrument_token not in token_map:
            token_map[row.instrument_token] = display
        seen_labels.add(display)

    return quote_keys, token_map


async def bootstrap_live_ticker() -> bool:
    """Stream index LTP via KiteTicker (OAuth) or REST polling (enctoken)."""
    set_tick_event_loop(asyncio.get_running_loop())

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

        quote_keys, token_map = await _resolve_index_maps(db)
        if not quote_keys:
            logger.warning("Live ticker: no index instruments in DB — run instrument sync")
            return False

        if account.auth_mode == "enctoken":
            await ticker_manager.stop()
            ltp_poller.set_targets(quote_keys)
            await ltp_poller.start(account)
            logger.info("Live LTP poller started for %s (%d indices)", account.label, len(quote_keys))
            return True

        api_key = decrypt_value(account.api_key_enc) if account.api_key_enc else ""
        session_token = (
            decrypt_value(account.access_token_enc) if account.access_token_enc else ""
        )
        if not api_key or not session_token:
            logger.warning(
                "Live ticker: Zerodha account %s missing api_key or access token",
                account.label,
            )
            return False

        await ltp_poller.stop()
        await ticker_manager.stop()
        ticker_manager.set_instruments(token_map)
        ticker_manager.set_publish_callback(publish_tick_threadsafe)
        await ticker_manager.start(session_token, api_key)
        logger.info("Live ticker started for %s (%d indices)", account.label, len(token_map))
        return True


def live_stream_active() -> bool:
    return ticker_manager.is_running or ltp_poller.is_running


async def ticker_watchdog() -> None:
    """Restart streaming if a session exists but nothing is running."""
    while True:
        await asyncio.sleep(60)
        try:
            if not live_stream_active():
                await bootstrap_live_ticker()
        except Exception:
            logger.exception("Ticker watchdog error")
