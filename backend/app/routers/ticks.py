import logging

from fastapi import APIRouter, Depends

from app.auth.jwt import get_current_user
from app.broker.ticker import RedisPubSub
from app.broker.ticker_service import (
    bootstrap_live_ticker,
    fetch_index_ltp_now,
    get_stream_status,
)
from app.broker.index_symbols import INDEX_DISPLAY_SYMBOLS
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ticks", tags=["ticks"])


@router.get("/snapshot")
async def tick_snapshot(_user: User = Depends(get_current_user)):
    """Latest index ticks — fetches from broker when cache is empty."""
    ticks: dict[str, dict] = {}
    missing: list[str] = []

    for sym in INDEX_DISPLAY_SYMBOLS:
        cached = await RedisPubSub.get_tick(sym)
        if cached:
            ticks[sym] = cached
        else:
            missing.append(sym)

    if missing:
        fresh = await fetch_index_ltp_now()
        for sym in missing:
            if sym in fresh:
                ticks[sym] = fresh[sym]
            else:
                cached = await RedisPubSub.get_tick(sym)
                if cached:
                    ticks[sym] = cached

    stream = await get_stream_status()
    return {"ticks": ticks, "stream": stream}


@router.post("/refresh")
async def refresh_ticks(_user: User = Depends(get_current_user)):
    """Force LTP fetch and restart background stream."""
    await bootstrap_live_ticker()
    ticks = await fetch_index_ltp_now()
    stream = await get_stream_status()
    return {"ticks": ticks, "stream": stream}
