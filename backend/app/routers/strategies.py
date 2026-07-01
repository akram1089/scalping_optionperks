from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_user
from app.db import get_db
from app.models import (
    AuditLog,
    BrokerAccount,
    GlobalState,
    Order,
    Position,
    RiskEvent,
    Signal,
    Strategy,
    StrategyAccount,
    Trade,
    User,
)
from app.schemas import (
    KillSwitchResponse,
    PnLResponse,
    PositionResponse,
    SignalResponse,
    StrategyCreate,
    StrategyResponse,
    StrategyUpdate,
    TradeResponse,
)

router = APIRouter(tags=["strategies", "dashboard"])


def _reject_equity(instrument_type: str | None) -> None:
    if instrument_type == "equity_intraday":
        raise HTTPException(
            status_code=400,
            detail="Equity strategies are not supported — use index futures or options",
        )


async def _strategy_response(db: AsyncSession, strategy: Strategy) -> StrategyResponse:
    result = await db.execute(
        select(StrategyAccount.broker_account_id).where(
            StrategyAccount.strategy_id == strategy.id, StrategyAccount.enabled.is_(True)
        )
    )
    account_ids = list(result.scalars().all())
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        instrument_type=strategy.instrument_type,
        symbol=strategy.symbol,
        entry_tf=strategy.entry_tf,
        htf=strategy.htf,
        params_json=strategy.params_json or {},
        risk_pct=strategy.risk_pct,
        rr_ratio=strategy.rr_ratio,
        atr_band_json=strategy.atr_band_json or {},
        spread_cap=strategy.spread_cap,
        avoid_open_min=strategy.avoid_open_min,
        avoid_close_min=strategy.avoid_close_min,
        max_trades_day=strategy.max_trades_day,
        daily_max_loss=strategy.daily_max_loss,
        consec_loss_limit=strategy.consec_loss_limit,
        enabled=strategy.enabled,
        paper_mode=strategy.paper_mode,
        running=strategy.running,
        broker_account_ids=account_ids,
    )


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.name)
    )
    strategies = result.scalars().all()
    return [await _strategy_response(db, s) for s in strategies]


@router.post("/strategies", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: StrategyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.params_json:
        body.params_json = {"rsi_length": 14, "wma_length": 21, "ema_length": 3, "mid_level": 50}
    if not body.atr_band_json:
        body.atr_band_json = {"min_atr": 0.5, "max_atr": 5.0}
    _reject_equity(body.instrument_type)

    strategy = Strategy(
        user_id=user.id,
        name=body.name,
        instrument_type=body.instrument_type,
        symbol=body.symbol,
        entry_tf=body.entry_tf,
        htf=body.htf,
        params_json=body.params_json,
        risk_pct=body.risk_pct,
        rr_ratio=body.rr_ratio,
        atr_band_json=body.atr_band_json,
        spread_cap=body.spread_cap,
        avoid_open_min=body.avoid_open_min,
        avoid_close_min=body.avoid_close_min,
        max_trades_day=body.max_trades_day,
        daily_max_loss=body.daily_max_loss,
        consec_loss_limit=body.consec_loss_limit,
        paper_mode=body.paper_mode,
        enabled=False,
    )
    db.add(strategy)
    await db.flush()

    for acc_id in body.broker_account_ids:
        db.add(StrategyAccount(strategy_id=strategy.id, broker_account_id=acc_id, enabled=True))

    db.add(
        AuditLog(
            user_id=user.id,
            action="strategy.create",
            target=str(strategy.id),
            meta_json={"name": body.name, "symbol": body.symbol},
        )
    )
    return await _strategy_response(db, strategy)


@router.patch("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: UUID,
    body: StrategyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await _get_user_strategy(db, user.id, strategy_id)
    for field, value in body.model_dump(exclude_unset=True, exclude={"broker_account_ids"}).items():
        setattr(strategy, field, value)

    if body.broker_account_ids is not None:
        await db.execute(
            StrategyAccount.__table__.delete().where(StrategyAccount.strategy_id == strategy_id)
        )
        for acc_id in body.broker_account_ids:
            db.add(StrategyAccount(strategy_id=strategy_id, broker_account_id=acc_id, enabled=True))

    return await _strategy_response(db, strategy)


@router.post("/strategies/{strategy_id}/start")
async def start_strategy(
    strategy_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await _get_user_strategy(db, user.id, strategy_id)
    gs = await _get_global_state(db)
    if gs.kill_switch:
        raise HTTPException(status_code=403, detail="Global kill switch is active")
    strategy.running = True
    strategy.enabled = True
    db.add(
        AuditLog(
            user_id=user.id,
            action="strategy.start",
            target=str(strategy_id),
            meta_json={"paper_mode": strategy.paper_mode},
        )
    )
    from app.engine.runtime import strategy_runtime

    await strategy_runtime.start_strategy(strategy_id)
    return {"status": "started", "strategy_id": str(strategy_id), "paper_mode": strategy.paper_mode}


@router.post("/strategies/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await _get_user_strategy(db, user.id, strategy_id)
    strategy.running = False
    db.add(AuditLog(user_id=user.id, action="strategy.stop", target=str(strategy_id), meta_json={}))
    from app.engine.runtime import strategy_runtime

    await strategy_runtime.stop_strategy(strategy_id)
    return {"status": "stopped", "strategy_id": str(strategy_id)}


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def activate_kill_switch(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import UTC, datetime

    gs = await _get_global_state(db)
    gs.kill_switch = True
    gs.kill_switch_at = datetime.now(UTC)
    result = await db.execute(select(Strategy).where(Strategy.user_id == user.id, Strategy.running))
    for strategy in result.scalars().all():
        strategy.running = False
    db.add(
        AuditLog(user_id=user.id, action="kill_switch.activate", target="global", meta_json={})
    )
    db.add(RiskEvent(event_type="kill_switch", detail="Global kill switch activated"))
    from app.engine.runtime import strategy_runtime

    await strategy_runtime.stop_all()
    from app.engine.fleet import flatten_all_positions

    await flatten_all_positions(db, user.id, paper_only=False)
    return KillSwitchResponse(kill_switch=gs.kill_switch, kill_switch_at=gs.kill_switch_at)


@router.post("/kill-switch/reset", response_model=KillSwitchResponse)
async def reset_kill_switch(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gs = await _get_global_state(db)
    gs.kill_switch = False
    gs.kill_switch_at = None
    db.add(AuditLog(user_id=user.id, action="kill_switch.reset", target="global", meta_json={}))
    return KillSwitchResponse(kill_switch=gs.kill_switch, kill_switch_at=gs.kill_switch_at)


@router.get("/kill-switch", response_model=KillSwitchResponse)
async def get_kill_switch(db: AsyncSession = Depends(get_db)):
    gs = await _get_global_state(db)
    return KillSwitchResponse(kill_switch=gs.kill_switch, kill_switch_at=gs.kill_switch_at)


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    account_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Position)
        .join(BrokerAccount)
        .where(BrokerAccount.user_id == user.id)
        .order_by(Position.updated_at.desc())
    )
    if account_id:
        query = query.where(Position.broker_account_id == account_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    account_id: UUID | None = None,
    strategy_id: UUID | None = None,
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Trade)
        .join(BrokerAccount)
        .where(BrokerAccount.user_id == user.id)
        .order_by(Trade.opened_at.desc())
        .limit(limit)
    )
    if account_id:
        query = query.where(Trade.broker_account_id == account_id)
    if strategy_id:
        query = query.where(Trade.strategy_id == strategy_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/signals", response_model=list[SignalResponse])
async def list_signals(
    strategy_id: UUID | None = None,
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Signal)
        .join(Strategy)
        .where(Strategy.user_id == user.id)
        .order_by(Signal.ts.desc())
        .limit(limit)
    )
    if strategy_id:
        query = query.where(Signal.strategy_id == strategy_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/pnl", response_model=list[PnLResponse])
async def get_pnl(
    account_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import UTC, datetime
    from decimal import Decimal

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    acc_query = select(BrokerAccount).where(BrokerAccount.user_id == user.id)
    if account_id:
        acc_query = acc_query.where(BrokerAccount.id == account_id)
    accounts = (await db.execute(acc_query)).scalars().all()
    responses = []
    for acc in accounts:
        trades = (
            await db.execute(
                select(Trade).where(
                    Trade.broker_account_id == acc.id, Trade.opened_at >= today_start
                )
            )
        ).scalars().all()
        realized = sum((t.pnl or Decimal(0)) for t in trades if t.closed_at)
        wins = sum(1 for t in trades if t.pnl and t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl and t.pnl < 0)
        positions = (
            await db.execute(select(Position).where(Position.broker_account_id == acc.id))
        ).scalars().all()
        unrealized = Decimal(0)
        responses.append(
            PnLResponse(
                account_id=acc.id,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                total_pnl=realized + unrealized,
                trades_today=len(trades),
                wins=wins,
                losses=losses,
            )
        )
    return responses


@router.get("/audit-log")
async def audit_log(
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.ts.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "action": l.action,
            "target": l.target,
            "meta": l.meta_json,
            "ts": l.ts.isoformat(),
        }
        for l in logs
    ]


async def _get_user_strategy(db: AsyncSession, user_id: UUID, strategy_id: UUID) -> Strategy:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


async def _get_global_state(db: AsyncSession) -> GlobalState:
    result = await db.execute(select(GlobalState).where(GlobalState.id == 1))
    gs = result.scalar_one_or_none()
    if not gs:
        gs = GlobalState(id=1, kill_switch=False)
        db.add(gs)
        await db.flush()
    return gs
