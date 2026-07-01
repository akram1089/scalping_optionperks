"""Start live index LTP when a Zerodha session is available."""

import asyncio
import logging

from sqlalchemy import select

from app.auth.crypto import decrypt_value
from app.broker.factory import account_session_active
from app.broker.ltp_poller import ltp_poller
from app.broker.ticker import RedisPubSub, publish_tick_threadsafe, set_tick_event_loop, ticker_manager
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


async def _get_connected_zerodha(db) -> BrokerAccount | None:
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.broker == "zerodha",
            BrokerAccount.enabled.is_(True),
        )
    )
    accounts = list(result.scalars().all())
    return next((a for a in accounts if account_session_active(a)), None)


def _payload_from_quote(q: dict, display: str) -> dict:
    ltp = q.get("last_price") or q.get("ltp")
    ohlc = q.get("ohlc") or {}
    prev = ohlc.get("close") or 0
    change_pct = ((ltp - prev) / prev * 100) if ltp and prev else 0
    return {
        "symbol": display,
        "ltp": ltp,
        "change_pct": change_pct,
        "volume": q.get("volume", 0),
    }


async def fetch_index_ltp_now() -> dict[str, dict]:
    """Fetch index LTP from Zerodha REST and publish to Redis (works for enctoken + OAuth)."""
    from app.broker.factory import get_broker_for_account

    async with async_session() as db:
        account = await _get_connected_zerodha(db)
        if not account:
            return {}

        quote_keys, _ = await _resolve_index_maps(db)
        if not quote_keys:
            return {}

        broker = get_broker_for_account(account)
        loop = asyncio.get_running_loop()
        try:
            quotes = await loop.run_in_executor(None, lambda: broker.ltp(list(quote_keys.keys())))
        except Exception:
            logger.exception("Index LTP fetch failed for %s", account.label)
            return {}
        finally:
            try:
                broker.close()
            except Exception:
                pass

        published: dict[str, dict] = {}
        for quote_key, display in quote_keys.items():
            q = quotes.get(quote_key) or {}
            if not q:
                continue
            payload = _payload_from_quote(q, display)
            if payload.get("ltp") is None:
                continue
            await RedisPubSub.publish_tick(display, {k: v for k, v in payload.items() if k != "symbol"})
            published[display] = payload
        return published


async def get_stream_status() -> dict:
    """Diagnostic info for the dashboard stream indicator."""
    async with async_session() as db:
        account = await _get_connected_zerodha(db)
        if not account:
            return {
                "active": False,
                "reason": "no_session",
                "message": "Connect a Zerodha account in Accounts",
            }
        quote_keys, _ = await _resolve_index_maps(db)
        if not quote_keys:
            return {
                "active": False,
                "reason": "no_instruments",
                "message": "Sync instruments in Settings, then refresh",
            }
        running = live_stream_active()
        mode = "enctoken_poll" if account.auth_mode == "enctoken" else "kite_ticker"
        return {
            "active": running,
            "reason": "running" if running else "starting",
            "message": "Live stream active" if running else "Fetching quotes from broker…",
            "mode": mode,
            "account": account.label,
        }


async def bootstrap_live_ticker() -> bool:
    """Stream index LTP via KiteTicker (OAuth) or REST polling (enctoken)."""
    set_tick_event_loop(asyncio.get_running_loop())

    async with async_session() as db:
        account = await _get_connected_zerodha(db)
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
            await fetch_index_ltp_now()
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
        await fetch_index_ltp_now()
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
            else:
                # Keep Redis cache warm even when stream is up
                await fetch_index_ltp_now()
        except Exception:
            logger.exception("Ticker watchdog error")
