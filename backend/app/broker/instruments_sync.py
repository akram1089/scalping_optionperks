"""Fetch and upsert Zerodha instrument master into PostgreSQL."""

import csv
import io
import logging
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import BrokerAccount, Instrument, InstrumentSyncLog

logger = logging.getLogger(__name__)

KITE_CSV_FIELDS = [
    "instrument_token",
    "exchange_token",
    "tradingsymbol",
    "name",
    "last_price",
    "expiry",
    "strike",
    "tick_size",
    "lot_size",
    "instrument_type",
    "segment",
    "exchange",
]


def _parse_decimal(value: str) -> Decimal | None:
    if not value or value.strip() == "":
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def _parse_int(value: str) -> int | None:
    if not value or value.strip() == "":
        return None
    try:
        return int(float(value.strip()))
    except ValueError:
        return None


def _parse_date(value: str) -> date | None:
    if not value or value.strip() == "":
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _row_to_dict(row: dict[str, str], sync_ts: datetime) -> dict[str, Any] | None:
    token = _parse_int(row.get("instrument_token", ""))
    exchange = (row.get("exchange") or "").strip()
    symbol = (row.get("tradingsymbol") or "").strip()
    if not token or not exchange or not symbol:
        return None
    lot = _parse_int(row.get("lot_size", "")) or 1
    return {
        "instrument_token": token,
        "exchange_token": _parse_int(row.get("exchange_token", "")),
        "tradingsymbol": symbol,
        "name": (row.get("name") or "").strip() or None,
        "last_price": _parse_decimal(row.get("last_price", "")),
        "expiry": _parse_date(row.get("expiry", "")),
        "strike": _parse_decimal(row.get("strike", "")),
        "tick_size": _parse_decimal(row.get("tick_size", "")),
        "lot_size": lot,
        "instrument_type": (row.get("instrument_type") or "").strip() or None,
        "segment": (row.get("segment") or "").strip() or None,
        "exchange": exchange,
        "is_active": True,
        "last_synced_at": sync_ts,
    }


async def fetch_instruments_csv(url: str | None = None) -> str:
    """Download instrument master CSV from Kite (public endpoint, no auth)."""
    settings = get_settings()
    target = url or settings.kite_instruments_url
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(target)
        response.raise_for_status()
        return response.text


async def fetch_instruments_via_api(db: AsyncSession) -> str:
    """Fallback: fetch via Kite Connect API using any account with a valid session."""
    from datetime import date as date_type

    from app.broker.session import account_session_active, get_broker_for_account

    today = date_type.today()
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.enabled.is_(True),
            BrokerAccount.token_date >= today,
        )
    )
    account = None
    for candidate in result.scalars().all():
        if account_session_active(candidate):
            account = candidate
            break
    if not account:
        raise RuntimeError("No broker account with active session for instrument API fallback")

    kite = get_broker_for_account(account)

    exchanges = ["NSE", "NFO", "BSE", "BFO", "CDS", "MCX"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=KITE_CSV_FIELDS)
    writer.writeheader()
    for exchange in exchanges:
        try:
            for inst in kite.instruments(exchange):
                writer.writerow(
                    {
                        "instrument_token": inst.get("instrument_token", ""),
                        "exchange_token": inst.get("exchange_token", ""),
                        "tradingsymbol": inst.get("tradingsymbol", ""),
                        "name": inst.get("name", ""),
                        "last_price": inst.get("last_price", ""),
                        "expiry": inst.get("expiry", ""),
                        "strike": inst.get("strike", ""),
                        "tick_size": inst.get("tick_size", ""),
                        "lot_size": inst.get("lot_size", ""),
                        "instrument_type": inst.get("instrument_type", ""),
                        "segment": inst.get("segment", ""),
                        "exchange": inst.get("exchange", exchange),
                    }
                )
        except Exception:
            logger.exception("Failed to fetch instruments for exchange %s", exchange)
    return buf.getvalue()


def parse_csv_rows(csv_text: str, sync_ts: datetime) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict[str, Any]] = []
    for row in reader:
        parsed = _row_to_dict(row, sync_ts)
        if parsed:
            rows.append(parsed)
    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last row wins per (exchange, tradingsymbol) within a sync batch."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        seen[(row["exchange"], row["tradingsymbol"])] = row
    return list(seen.values())


async def upsert_instruments(db: AsyncSession, rows: list[dict[str, Any]]) -> int:
    settings = get_settings()
    batch_size = settings.instrument_sync_batch_size
    rows = dedupe_rows(rows)
    total = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        stmt = insert(Instrument).values(batch)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=["exchange", "tradingsymbol"],
            set_={
                "instrument_token": excluded.instrument_token,
                "exchange_token": excluded.exchange_token,
                "name": excluded.name,
                "last_price": excluded.last_price,
                "expiry": excluded.expiry,
                "strike": excluded.strike,
                "tick_size": excluded.tick_size,
                "lot_size": excluded.lot_size,
                "instrument_type": excluded.instrument_type,
                "segment": excluded.segment,
                "is_active": True,
                "last_synced_at": excluded.last_synced_at,
            },
        )
        await db.execute(stmt)
        total += len(batch)

    return total


async def deactivate_stale_instruments(db: AsyncSession, sync_ts: datetime) -> int:
    result = await db.execute(
        update(Instrument)
        .where(Instrument.last_synced_at < sync_ts, Instrument.is_active.is_(True))
        .values(is_active=False)
    )
    return result.rowcount or 0


async def sync_instruments(db: AsyncSession, source: str = "kite_csv") -> InstrumentSyncLog:
    """Full sync: download latest master, upsert, deactivate removed instruments."""
    sync_ts = datetime.now(UTC)
    log = InstrumentSyncLog(status="running", source=source, started_at=sync_ts)
    db.add(log)
    await db.flush()

    try:
        csv_text = await fetch_instruments_csv()
    except Exception as csv_err:
        logger.warning("Kite CSV fetch failed (%s), trying API fallback", csv_err)
        try:
            csv_text = await fetch_instruments_via_api(db)
            log.source = "kite_api"
        except Exception as api_err:
            log.status = "failed"
            log.finished_at = datetime.now(UTC)
            log.error_detail = f"CSV: {csv_err}; API: {api_err}"
            logger.exception("Instrument sync failed")
            return log

    rows = parse_csv_rows(csv_text, sync_ts)
    if not rows:
        log.status = "failed"
        log.finished_at = datetime.now(UTC)
        log.error_detail = "No instrument rows parsed from source"
        return log

    upserted = await upsert_instruments(db, rows)
    deactivated = await deactivate_stale_instruments(db, sync_ts)

    log.status = "success"
    log.rows_upserted = upserted
    log.rows_deactivated = deactivated
    log.finished_at = datetime.now(UTC)
    logger.info(
        "Instrument sync complete: %d upserted, %d deactivated (source=%s)",
        upserted,
        deactivated,
        log.source,
    )
    return log


async def run_instrument_sync_job() -> None:
    from app.db import async_session

    logger.info("Instrument sync job started")
    async with async_session() as db:
        await sync_instruments(db)
        await db.commit()
