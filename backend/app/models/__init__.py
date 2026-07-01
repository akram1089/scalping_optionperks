import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    broker_accounts: Mapped[list["BrokerAccount"]] = relationship(back_populates="user")
    strategies: Mapped[list["Strategy"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(100))
    broker: Mapped[str] = mapped_column(String(50), default="zerodha")
    auth_mode: Mapped[str] = mapped_column(String(20), default="kite_connect")
    api_key_enc: Mapped[str] = mapped_column(Text)
    api_secret_enc: Mapped[str] = mapped_column(Text)
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    zerodha_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pin_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100000"))
    auto_login: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    enctoken_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="broker_accounts")
    orders: Mapped[list["Order"]] = relationship(back_populates="broker_account")
    trades: Mapped[list["Trade"]] = relationship(back_populates="broker_account")
    positions: Mapped[list["Position"]] = relationship(back_populates="broker_account")


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    instrument_type: Mapped[str] = mapped_column(String(50), default="futures")
    symbol: Mapped[str] = mapped_column(String(50))
    entry_tf: Mapped[str] = mapped_column(String(10), default="5minute")
    htf: Mapped[str] = mapped_column(String(10), default="15minute")
    params_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0"))
    rr_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("2.0"))
    atr_band_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    spread_cap: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.5"))
    avoid_open_min: Mapped[int] = mapped_column(Integer, default=15)
    avoid_close_min: Mapped[int] = mapped_column(Integer, default=15)
    max_trades_day: Mapped[int] = mapped_column(Integer, default=10)
    daily_max_loss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("5000"))
    consec_loss_limit: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    paper_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    running: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="strategies")
    strategy_accounts: Mapped[list["StrategyAccount"]] = relationship(back_populates="strategy")
    signals: Mapped[list["Signal"]] = relationship(back_populates="strategy")
    orders: Mapped[list["Order"]] = relationship(back_populates="strategy")
    trades: Mapped[list["Trade"]] = relationship(back_populates="strategy")


class StrategyAccount(Base):
    __tablename__ = "strategy_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"))
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    strategy: Mapped["Strategy"] = relationship(back_populates="strategy_accounts")
    broker_account: Mapped["BrokerAccount"] = relationship()


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    side: Mapped[str] = mapped_column(String(10))
    tf: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    indicator_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    acted: Mapped[bool] = mapped_column(Boolean, default=False)
    paper: Mapped[bool] = mapped_column(Boolean, default=True)

    strategy: Mapped["Strategy"] = relationship(back_populates="signals")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    side: Mapped[str] = mapped_column(String(10))
    symbol: Mapped[str] = mapped_column(String(50))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    order_type: Mapped[str] = mapped_column(String(20), default="LIMIT")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    parent_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    paper: Mapped[bool] = mapped_column(Boolean, default=True)

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="orders")
    strategy: Mapped["Strategy | None"] = relationship(back_populates="orders")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    entry_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    exit_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    side: Mapped[str] = mapped_column(String(10))
    symbol: Mapped[str] = mapped_column(String(50))
    qty: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paper: Mapped[bool] = mapped_column(Boolean, default=True)

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="trades")
    strategy: Mapped["Strategy | None"] = relationship(back_populates="trades")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String(50))
    qty: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    side: Mapped[str] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    paper: Mapped[bool] = mapped_column(Boolean, default=True)

    broker_account: Mapped["BrokerAccount"] = relationship(back_populates="positions")


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    broker_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="SET NULL"), nullable=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column("type", String(50))
    detail: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="audit_logs")


class GlobalState(Base):
    """Singleton-style global kill switch and runtime flags."""

    __tablename__ = "global_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Instrument(Base):
    """Zerodha instrument master — synced daily from Kite instruments dump."""

    __tablename__ = "instruments"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    tradingsymbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    instrument_token: Mapped[int] = mapped_column(Integer, index=True)
    exchange_token: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    instrument_type: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    segment: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InstrumentSyncLog(Base):
    """Audit trail for daily instrument master sync runs."""

    __tablename__ = "instrument_sync_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    source: Mapped[str] = mapped_column(String(50), default="kite_csv")
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_deactivated: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
