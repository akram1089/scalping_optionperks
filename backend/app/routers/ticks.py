import logging

from fastapi import APIRouter, Depends

from app.auth.jwt import get_current_user
from app.broker.ticker import RedisPubSub
from app.broker.ticker_service import INDEX_DISPLAY_SYMBOLS
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ticks", tags=["ticks"])


@router.get("/snapshot")
async def tick_snapshot(_user: User = Depends(get_current_user)):
    """Latest cached index ticks for dashboard hydration."""
    ticks: dict[str, dict] = {}
    for sym in INDEX_DISPLAY_SYMBOLS:
        cached = await RedisPubSub.get_tick(sym)
        if cached:
            ticks[sym] = cached
    return {"ticks": ticks}
