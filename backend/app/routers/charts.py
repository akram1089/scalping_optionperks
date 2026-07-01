"""Chart data — historical candles from connected broker session."""

import logging
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.broker.session import account_session_active, get_broker_for_account
from app.db import get_db
from app.models import BrokerAccount, User
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/charts", tags=["charts"])
IST = ZoneInfo("Asia/Kolkata")

VALID_INTERVALS = {
    "minute",
    "3minute",
    "5minute",
    "10minute",
    "15minute",
    "30minute",
    "60minute",
    "day",
}


class CandlePoint(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartCandlesResponse(BaseModel):
    tradingsymbol: str
    exchange: str
    instrument_token: int
    interval: str
    live: bool
    candles: list[CandlePoint]


async def _resolve_account(
    db: AsyncSession, user_id: UUID, account_id: UUID | None
) -> BrokerAccount:
    if account_id:
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.id == account_id,
                BrokerAccount.user_id == user_id,
                BrokerAccount.enabled.is_(True),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account

    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.user_id == user_id,
            BrokerAccount.enabled.is_(True),
        ).order_by(BrokerAccount.label)
    )
    for account in result.scalars().all():
        if account_session_active(account):
            return account
    raise HTTPException(status_code=400, detail="No connected broker account — reconnect in Accounts")


def _parse_candle_time(raw: str | datetime) -> int:
    if isinstance(raw, datetime):
        dt = raw
    else:
        s = str(raw).replace("T", " ").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s[:19], fmt[: len(s) if len(s) < 19 else 19])
                break
            except ValueError:
                continue
        else:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return int(dt.timestamp())


@router.get("/candles", response_model=ChartCandlesResponse)
async def get_chart_candles(
    instrument_token: int = Query(...),
    tradingsymbol: str = Query(...),
    exchange: str = Query("NSE"),
    interval: str = Query("5minute"),
    days: int = Query(5, ge=1, le=60),
    account_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Use one of: {sorted(VALID_INTERVALS)}")

    account = await _resolve_account(db, user.id, account_id)
    if not account_session_active(account):
        raise HTTPException(status_code=400, detail="Broker session expired — reconnect in Accounts")

    broker = None
    try:
        broker = get_broker_for_account(account)
        to_dt = datetime.now(IST)
        from_dt = to_dt - timedelta(days=days)
        from_str = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        to_str = to_dt.strftime("%Y-%m-%d %H:%M:%S")
        raw = broker.historical_data(exchange.upper(), tradingsymbol, from_str, to_str, interval)
    except Exception as exc:
        logger.exception("Chart candle fetch failed")
        raise HTTPException(status_code=502, detail=f"Failed to fetch candles: {exc}") from exc
    finally:
        if broker is not None:
            broker.close()

    candles: list[CandlePoint] = []
    for row in raw:
        try:
            candles.append(
                CandlePoint(
                    time=_parse_candle_time(row["date"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    candles.sort(key=lambda c: c.time)

    return ChartCandlesResponse(
        tradingsymbol=tradingsymbol,
        exchange=exchange.upper(),
        instrument_token=instrument_token,
        interval=interval,
        live=True,
        candles=candles,
    )
