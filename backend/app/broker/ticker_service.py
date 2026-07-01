"""Start live index LTP when a Zerodha session is available."""

import asyncio
import logging

from sqlalchemy import select

from app.broker.factory import account_session_active, get_broker_for_account
from app.broker.index_symbols import INDEX_DISPLAY_SYMBOLS, INDEX_INSTRUMENT_TOKENS
from app.broker.ltp_fetch import fetch_all_index_ltp_historical, fetch_all_index_ltp_oauth
from app.broker.ticker import RedisPubSub, publish_tick_threadsafe, set_tick_event_loop, ticker_manager
from app.broker.zerodha_ws import zerodha_ticker_credentials
from app.db import async_session
from app.models import BrokerAccount, Instrument

logger = logging.getLogger(__name__)

__all__ = ["INDEX_DISPLAY_SYMBOLS", "bootstrap_live_ticker", "fetch_index_ltp_now", "get_stream_status"]

_INDEX_TARGETS: list[tuple[str, str, str]] = [
    ("NIFTY 50", "NSE", "NIFTY 50"),
    ("NIFTY 50", "NSE", "NIFTY"),
    ("BANK NIFTY", "NSE", "NIFTY BANK"),
    ("BANK NIFTY", "NSE", "BANKNIFTY"),
    ("SENSEX", "BSE", "SENSEX"),
]


async def _resolve_index_maps(
    db,
) -> tuple[dict[str, str], dict[int, str]]:
    quote_keys: dict[str, str] = {}
    token_map: dict[int, str] = dict(INDEX_INSTRUMENT_TOKENS)
    seen_labels: set[str] = set(token_map.values())

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


async def _publish_quotes(quotes: dict[str, dict]) -> dict[str, dict]:
    published: dict[str, dict] = {}
    for display, q in quotes.items():
        payload = _payload_from_quote(q, display)
        if payload.get("ltp") is None:
            continue
        await RedisPubSub.publish_tick(
            display, {k: v for k, v in payload.items() if k != "symbol"}
        )
        published[display] = payload
    return published


async def _cached_index_ticks() -> dict[str, dict]:
    ticks: dict[str, dict] = {}
    for sym in INDEX_DISPLAY_SYMBOLS:
        cached = await RedisPubSub.get_tick(sym)
        if cached:
            ticks[sym] = cached
    return ticks


async def fetch_index_ltp_now() -> dict[str, dict]:
    """Fetch index LTP — OAuth uses REST; enctoken uses Redis cache + historical fallback."""
    async with async_session() as db:
        account = await _get_connected_zerodha(db)
        if not account:
            return {}

        cached = await _cached_index_ticks()
        if len(cached) >= len(INDEX_DISPLAY_SYMBOLS):
            return cached

        _, token_map = await _resolve_index_maps(db)
        loop = asyncio.get_running_loop()
        quotes: dict[str, dict] = {}

        if account.auth_mode == "enctoken":
            # REST /quote and /quote/ltp return 400 for enctoken — use historical OMS API
            broker = get_broker_for_account(account)
            try:
                quotes = await fetch_all_index_ltp_historical(broker._inner, token_map, loop)
            except Exception:
                logger.exception("Historical index LTP failed for %s", account.label)
            finally:
                try:
                    broker.close()
                except Exception:
                    pass
        else:
            broker = get_broker_for_account(account)
            try:
                quotes = await fetch_all_index_ltp_oauth(broker, loop)
            except Exception:
                logger.exception("Index LTP fetch failed for %s", account.label)
            finally:
                try:
                    broker.close()
                except Exception:
                    pass

        published = await _publish_quotes(quotes)
        published.update({k: v for k, v in cached.items() if k not in published})
        if not published and account.auth_mode == "enctoken":
            logger.warning(
                "No index LTP for %s — ensure KiteTicker WebSocket is running (market hours)",
                account.label,
            )
        return published


async def get_stream_status() -> dict:
    async with async_session() as db:
        account = await _get_connected_zerodha(db)
        if not account:
            return {
                "active": False,
                "reason": "no_session",
                "message": "Connect a Zerodha account in Accounts",
            }

        running = live_stream_active()
        if account.auth_mode == "enctoken":
            mode = "enctoken_ws"
            if running:
                msg = "Live WebSocket stream active"
            else:
                msg = "Starting WebSocket stream (enctoken — REST quotes not available)"
        else:
            mode = "kite_ticker"
            msg = "Live stream active" if running else "Fetching quotes from broker…"

        return {
            "active": running,
            "reason": "running" if running else "starting",
            "message": msg,
            "mode": mode,
            "account": account.label,
        }


async def _start_kite_ticker(account: BrokerAccount, token_map: dict[int, str]) -> bool:
    creds = zerodha_ticker_credentials(account)
    if not creds:
        logger.warning("Cannot start KiteTicker for %s — missing credentials", account.label)
        return False
    api_key, session_token = creds
    await ticker_manager.stop()
    ticker_manager.set_instruments(token_map)
    ticker_manager.set_publish_callback(publish_tick_threadsafe)
    await ticker_manager.start(session_token, api_key)
    return True


async def bootstrap_live_ticker() -> bool:
    """Stream index LTP via KiteTicker (OAuth + enctoken WebSocket)."""
    set_tick_event_loop(asyncio.get_running_loop())

    async with async_session() as db:
        account = await _get_connected_zerodha(db)
        if not account:
            logger.info("Live ticker: no connected Zerodha account")
            return False

        _, token_map = await _resolve_index_maps(db)
        if not token_map:
            logger.warning("Live ticker: no index tokens available")
            return False

        started = await _start_kite_ticker(account, token_map)
        if started:
            await fetch_index_ltp_now()
            logger.info(
                "KiteTicker started for %s (%d indices, auth=%s)",
                account.label,
                len(token_map),
                account.auth_mode,
            )
        return started


def live_stream_active() -> bool:
    return ticker_manager.is_running


async def ticker_watchdog() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            if not live_stream_active():
                await bootstrap_live_ticker()
            elif not await _cached_index_ticks():
                await fetch_index_ltp_now()
        except Exception:
            logger.exception("Ticker watchdog error")
