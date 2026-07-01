from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BrokerAccountCreate(BaseModel):
    label: str
    broker: Literal["zerodha", "angel_one", "fyers", "kotak", "ventura"] = "zerodha"
    auth_mode: Literal["kite_connect", "enctoken", "smartapi", "oauth", "totp", "sso"] = "kite_connect"
    api_key: str | None = None
    api_secret: str | None = None
    zerodha_password: str | None = None
    pin: str | None = None
    totp_secret: str | None = None
    zerodha_user_id: str | None = None
    client_id: str | None = None
    capital: Decimal = Decimal("100000")
    auto_login: bool = False


class BrokerAccountUpdate(BaseModel):
    label: str | None = None
    capital: Decimal | None = None
    zerodha_user_id: str | None = None
    client_id: str | None = None
    zerodha_password: str | None = None
    pin: str | None = None
    totp_secret: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    auto_login: bool | None = None
    enabled: bool | None = None


class BrokerListResponse(BaseModel):
    slug: str
    label: str
    auth_modes: list[str]
    required_fields: dict[str, list[str]]
    connect_type: str


class AccountLimitsResponse(BaseModel):
    max_accounts: int
    current_count: int


class BrokerMarginsInfo(BaseModel):
    net: float
    available_cash: float
    opening_balance: float
    collateral: float
    utilised_debits: float
    m2m_unrealised: float
    m2m_realised: float


class BrokerPositionsInfo(BaseModel):
    open_positions: int
    day_trades: int
    unrealised_pnl: float


class BrokerLiveInfoResponse(BaseModel):
    user_id: str | None = None
    user_name: str | None = None
    email: str | None = None
    broker: str | None = None
    exchanges: list[str] = []
    products: list[str] = []
    order_types: list[str] = []
    margins: BrokerMarginsInfo
    holdings_count: int
    holdings_value: float
    positions: BrokerPositionsInfo


class EnctokenConnectRequest(BaseModel):
    """Paste enctoken from browser cookies, or leave empty to auto-login with stored creds."""
    enctoken: str | None = None
    twofa_code: str | None = None


class FyersCallbackRequest(BaseModel):
    auth_code: str
    state: str | None = None


class VenturaCallbackRequest(BaseModel):
    request_token: str
    state: str | None = None


class BrokerAccountResponse(BaseModel):
    id: UUID
    label: str
    broker: str
    auth_mode: str = "kite_connect"
    zerodha_user_id: str | None
    client_id: str | None = None
    capital: Decimal
    auto_login: bool
    enabled: bool
    totp_configured: bool = False
    token_date: date | None = None
    session_active: bool = False

    model_config = {"from_attributes": True}


class ConnectResponse(BaseModel):
    login_url: str
    account_id: UUID


class StrategyParams(BaseModel):
    rsi_length: int = 14
    wma_length: int = 21
    ema_length: int = 3
    mid_level: float = 50.0


class AtrBand(BaseModel):
    min_atr: float = 0.5
    max_atr: float = 5.0


class StrategyCreate(BaseModel):
    name: str
    instrument_type: str = "futures"
    symbol: str
    entry_tf: str = "5minute"
    htf: str = "15minute"
    params_json: dict = Field(default_factory=dict)
    risk_pct: Decimal = Decimal("1.0")
    rr_ratio: Decimal = Decimal("2.0")
    atr_band_json: dict = Field(default_factory=dict)
    spread_cap: Decimal = Decimal("0.5")
    avoid_open_min: int = 15
    avoid_close_min: int = 15
    max_trades_day: int = 10
    daily_max_loss: Decimal = Decimal("5000")
    consec_loss_limit: int = 3
    paper_mode: bool = True
    broker_account_ids: list[UUID] = Field(default_factory=list)


class StrategyUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    entry_tf: str | None = None
    htf: str | None = None
    params_json: dict | None = None
    risk_pct: Decimal | None = None
    rr_ratio: Decimal | None = None
    atr_band_json: dict | None = None
    spread_cap: Decimal | None = None
    avoid_open_min: int | None = None
    avoid_close_min: int | None = None
    max_trades_day: int | None = None
    daily_max_loss: Decimal | None = None
    consec_loss_limit: int | None = None
    paper_mode: bool | None = None
    enabled: bool | None = None
    broker_account_ids: list[UUID] | None = None


class StrategyResponse(BaseModel):
    id: UUID
    name: str
    instrument_type: str
    symbol: str
    entry_tf: str
    htf: str
    params_json: dict
    risk_pct: Decimal
    rr_ratio: Decimal
    atr_band_json: dict
    spread_cap: Decimal
    avoid_open_min: int
    avoid_close_min: int
    max_trades_day: int
    daily_max_loss: Decimal
    consec_loss_limit: int
    enabled: bool
    paper_mode: bool
    running: bool
    broker_account_ids: list[UUID] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SignalResponse(BaseModel):
    id: UUID
    strategy_id: UUID
    ts: datetime
    side: str
    tf: str
    price: Decimal
    indicator_snapshot_json: dict
    acted: bool
    paper: bool

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    symbol: str
    qty: int
    avg_price: Decimal
    side: str
    stop_loss: Decimal | None
    target: Decimal | None
    paper: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class TradeResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    strategy_id: UUID | None
    side: str
    symbol: str
    qty: int
    entry_price: Decimal
    exit_price: Decimal | None
    pnl: Decimal | None
    exit_reason: str | None
    opened_at: datetime
    closed_at: datetime | None
    paper: bool

    model_config = {"from_attributes": True}


class PnLResponse(BaseModel):
    account_id: UUID
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    trades_today: int
    wins: int
    losses: int


class KillSwitchResponse(BaseModel):
    kill_switch: bool
    kill_switch_at: datetime | None
