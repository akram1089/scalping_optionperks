from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.broker.instruments_sync import run_instrument_sync_job, sync_instruments
from app.db import get_db
from app.models import Instrument, InstrumentSyncLog, User
from pydantic import BaseModel

router = APIRouter(prefix="/instruments", tags=["instruments"])


class InstrumentResponse(BaseModel):
    instrument_token: int
    exchange: str
    tradingsymbol: str
    name: str | None
    lot_size: int
    instrument_type: str | None
    segment: str | None
    expiry: date | None = None
    strike: float | None = None
    tick_size: float | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class SyncLogResponse(BaseModel):
    id: UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    source: str
    rows_upserted: int
    rows_deactivated: int
    error_detail: str | None

    model_config = {"from_attributes": True}


class SyncResultResponse(BaseModel):
    status: str
    rows_upserted: int
    rows_deactivated: int
    source: str
    sync_log_id: UUID


@router.get("", response_model=list[InstrumentResponse])
async def search_instruments(
    exchange: str | None = Query(None, description="NSE, NFO, BSE, etc."),
    segment: str | None = None,
    instrument_type: str | None = Query(None, description="EQ, FUT, CE, PE, etc."),
    underlying: str | None = Query(None, description="Underlying name e.g. NIFTY, BANKNIFTY"),
    expiry: date | None = Query(None, description="Expiry date for F&O"),
    strike: float | None = Query(None, description="Strike price for options"),
    q: str | None = Query(None, description="Search tradingsymbol or name"),
    active_only: bool = True,
    limit: int = Query(50, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Instrument).order_by(Instrument.tradingsymbol)
    if active_only:
        query = query.where(Instrument.is_active.is_(True))
    if exchange:
        query = query.where(Instrument.exchange == exchange.upper())
    if segment:
        query = query.where(Instrument.segment == segment.upper())
    if instrument_type:
        types = [t.strip().upper() for t in instrument_type.split(",")]
        if len(types) == 1:
            query = query.where(Instrument.instrument_type == types[0])
        else:
            query = query.where(Instrument.instrument_type.in_(types))
    if underlying:
        u = underlying.upper()
        query = query.where(
            or_(
                func.upper(Instrument.name) == u,
                func.upper(Instrument.tradingsymbol).like(f"{u}%"),
            )
        )
    if expiry:
        query = query.where(Instrument.expiry == expiry)
    if strike is not None:
        query = query.where(Instrument.strike == strike)
    if q:
        pattern = f"%{q.upper()}%"
        query = query.where(
            or_(
                func.upper(Instrument.tradingsymbol).like(pattern),
                func.upper(Instrument.name).like(pattern),
            )
        )
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/underlyings")
async def list_underlyings(
    exchange: str = Query("NFO"),
    instrument_type: str | None = Query(None, description="FUT, CE, PE or CE,PE"),
    index_only: bool = Query(False, description="Index underlyings only (NIFTY, BANKNIFTY, …)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Distinct underlying names for F&O instrument selection."""
    query = (
        select(Instrument.name, func.count())
        .where(Instrument.is_active.is_(True), Instrument.exchange == exchange.upper())
        .where(Instrument.name.isnot(None), Instrument.name != "")
    )
    if instrument_type:
        types = [t.strip().upper() for t in instrument_type.split(",")]
        query = query.where(Instrument.instrument_type.in_(types))
    if index_only:
        index_names = ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "SENSEX", "BANKEX")
        query = query.where(func.upper(Instrument.name).in_(index_names))
    query = query.group_by(Instrument.name).order_by(Instrument.name)
    result = await db.execute(query)
    return [{"underlying": row[0], "count": row[1]} for row in result.all()]


@router.get("/expiries", response_model=list[date])
async def list_expiries(
    underlying: str = Query(..., description="e.g. NIFTY"),
    exchange: str = Query("NFO"),
    instrument_type: str = Query("CE,PE", description="CE, PE, FUT or comma-separated"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = underlying.upper()
    types = [t.strip().upper() for t in instrument_type.split(",")]
    result = await db.execute(
        select(Instrument.expiry)
        .where(
            Instrument.is_active.is_(True),
            Instrument.exchange == exchange.upper(),
            Instrument.instrument_type.in_(types),
            Instrument.expiry.isnot(None),
            or_(
                func.upper(Instrument.name) == u,
                func.upper(Instrument.tradingsymbol).like(f"{u}%"),
            ),
        )
        .distinct()
        .order_by(Instrument.expiry)
    )
    return [row[0] for row in result.all() if row[0]]


@router.get("/strikes", response_model=list[InstrumentResponse])
async def list_strikes(
    underlying: str = Query(..., description="e.g. NIFTY"),
    expiry: date = Query(...),
    option_type: str = Query("CE", description="CE or PE"),
    exchange: str = Query("NFO"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Strike chain for an underlying + expiry — ordered by strike ascending."""
    u = underlying.upper()
    opt = option_type.upper()
    result = await db.execute(
        select(Instrument)
        .where(
            Instrument.is_active.is_(True),
            Instrument.exchange == exchange.upper(),
            Instrument.instrument_type == opt,
            Instrument.expiry == expiry,
            Instrument.strike.isnot(None),
            or_(
                func.upper(Instrument.name) == u,
                func.upper(Instrument.tradingsymbol).like(f"{u}%"),
            ),
        )
        .order_by(Instrument.strike)
    )
    return result.scalars().all()


@router.get("/exchanges")
async def list_exchanges(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Instrument.exchange, func.count())
        .where(Instrument.is_active.is_(True))
        .group_by(Instrument.exchange)
        .order_by(Instrument.exchange)
    )
    return [{"exchange": row[0], "count": row[1]} for row in result.all()]


@router.get("/sync/status", response_model=SyncLogResponse | None)
async def latest_sync_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InstrumentSyncLog).order_by(InstrumentSyncLog.started_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/sync/history", response_model=list[SyncLogResponse])
async def sync_history(
    limit: int = Query(20, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InstrumentSyncLog).order_by(InstrumentSyncLog.started_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/sync", response_model=SyncResultResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual trigger — useful on first VPS deploy before 08:50 IST job runs."""
    log = await sync_instruments(db)
    if log.status == "failed":
        raise HTTPException(status_code=502, detail=log.error_detail or "Sync failed")
    return SyncResultResponse(
        status=log.status,
        rows_upserted=log.rows_upserted,
        rows_deactivated=log.rows_deactivated,
        source=log.source,
        sync_log_id=log.id,
    )
