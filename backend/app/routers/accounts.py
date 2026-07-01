import logging
from datetime import date
from uuid import UUID

import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import decrypt_value, encrypt_value
from app.auth.jwt import get_current_user
from app.broker.angel.adapter import angel_login
from app.broker.enctoken_client import EnctokenService, EnctokenSessionError, normalize_enctoken
from app.broker.enctoken_login import EnctokenLoginService, normalize_totp_secret
from app.broker.factory import account_session_active, get_broker_for_account
from app.broker.fyers.adapter import fyers_generate_token, fyers_login_url
from app.broker.kite_client import KiteService
from app.broker.kotak.adapter import kotak_login
from app.broker.registry import list_brokers
from app.broker.ticker_service import bootstrap_live_ticker
from app.broker.ventura.adapter import ventura_generate_token, ventura_sso_url, ventura_totp_login
from app.config import get_settings
from app.db import get_db
from app.models import AuditLog, BrokerAccount, User
from app.schemas import (
    AccountLimitsResponse,
    BrokerAccountCreate,
    BrokerAccountResponse,
    BrokerAccountUpdate,
    BrokerListResponse,
    BrokerLiveInfoResponse,
    ConnectResponse,
    EnctokenConnectRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])

_pending_connect: dict[str, UUID] = {}
_pending_fyers: dict[str, UUID] = {}
_pending_ventura: dict[str, UUID] = {}


def _schedule_ticker_restart(background_tasks: BackgroundTasks) -> None:
    background_tasks.add_task(bootstrap_live_ticker)


@router.post("/live-ticker/bootstrap")
async def restart_live_ticker(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Start or restart Kite index LTP stream using the first connected Zerodha account."""
    background_tasks.add_task(bootstrap_live_ticker)
    return {"status": "starting"}


def _account_response(account: BrokerAccount) -> BrokerAccountResponse:
    return BrokerAccountResponse(
        id=account.id,
        label=account.label,
        broker=account.broker,
        auth_mode=account.auth_mode,
        zerodha_user_id=account.zerodha_user_id,
        client_id=account.client_id,
        capital=account.capital,
        auto_login=account.auto_login,
        enabled=account.enabled,
        totp_configured=bool(account.totp_secret_enc),
        token_date=account.token_date,
        session_active=account_session_active(account),
    )


def _totp_code(secret_enc: str | None) -> str:
    if not secret_enc:
        raise HTTPException(status_code=400, detail="TOTP secret required")
    secret = normalize_totp_secret(decrypt_value(secret_enc))
    return pyotp.TOTP(secret).now()


def _resolve_auth_mode(body: BrokerAccountCreate) -> str:
    broker = body.broker
    if broker == "angel_one":
        return "smartapi"
    if broker == "fyers":
        return "oauth"
    if broker == "kotak":
        return "totp"
    if broker == "ventura":
        return "totp" if body.client_id and body.totp_secret else "sso"
    return body.auth_mode


def _validate_broker_create(body: BrokerAccountCreate) -> None:
    broker = body.broker
    if broker == "zerodha":
        if body.auth_mode == "kite_connect":
            if not body.api_key or not body.api_secret:
                raise HTTPException(status_code=400, detail="API key and secret required for Kite Connect")
        elif body.auth_mode == "enctoken":
            if not body.zerodha_user_id:
                raise HTTPException(status_code=400, detail="Zerodha user ID required for enctoken mode")
            if not body.zerodha_password:
                raise HTTPException(status_code=400, detail="Zerodha password required for enctoken auto-login")
            if not body.totp_secret:
                raise HTTPException(status_code=400, detail="TOTP secret required for enctoken auto-login")
    elif broker == "angel_one":
        if not body.api_key:
            raise HTTPException(status_code=400, detail="Angel API key required")
        if not body.client_id:
            raise HTTPException(status_code=400, detail="Angel client code required")
        if not body.pin:
            raise HTTPException(status_code=400, detail="Angel MPIN required")
        if not body.totp_secret:
            raise HTTPException(status_code=400, detail="TOTP secret required for Angel One")
    elif broker == "fyers":
        if not body.api_key or not body.api_secret:
            raise HTTPException(status_code=400, detail="Fyers App ID and secret required")
    elif broker == "kotak":
        if not body.api_key:
            raise HTTPException(status_code=400, detail="Kotak consumer key required")
        if not body.client_id:
            raise HTTPException(status_code=400, detail="Kotak UCC/client ID required")
        if not body.zerodha_password:
            raise HTTPException(status_code=400, detail="Kotak MPIN required")
        if not body.totp_secret:
            raise HTTPException(status_code=400, detail="TOTP secret required for Kotak")
    elif broker == "ventura":
        if not body.api_key or not body.api_secret:
            raise HTTPException(status_code=400, detail="Ventura app key and secret required")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported broker: {broker}")

    if body.auto_login and not body.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP secret required when auto-login is enabled")


@router.get("/brokers", response_model=list[BrokerListResponse])
async def get_brokers():
    return [BrokerListResponse(**b) for b in list_brokers()]


@router.get("/limits", response_model=AccountLimitsResponse)
async def get_account_limits(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    result = await db.execute(
        select(func.count()).select_from(BrokerAccount).where(BrokerAccount.user_id == user.id)
    )
    count = result.scalar() or 0
    return AccountLimitsResponse(max_accounts=settings.max_accounts_per_user, current_count=count)


@router.get("", response_model=list[BrokerAccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.user_id == user.id).order_by(BrokerAccount.label)
    )
    return [_account_response(a) for a in result.scalars().all()]


@router.post("", response_model=BrokerAccountResponse, status_code=status.HTTP_201_CREATED)
async def add_account(
    body: BrokerAccountCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    count_result = await db.execute(
        select(func.count()).select_from(BrokerAccount).where(BrokerAccount.user_id == user.id)
    )
    if (count_result.scalar() or 0) >= settings.max_accounts_per_user:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_accounts_per_user} broker accounts allowed",
        )

    _validate_broker_create(body)
    auth_mode = _resolve_auth_mode(body)
    totp_secret = normalize_totp_secret(body.totp_secret) if body.totp_secret else None

    account = BrokerAccount(
        user_id=user.id,
        label=body.label,
        broker=body.broker,
        auth_mode=auth_mode,
        api_key_enc=encrypt_value(body.api_key or ""),
        api_secret_enc=encrypt_value(body.api_secret or ""),
        password_enc=encrypt_value(body.zerodha_password) if body.zerodha_password else None,
        pin_enc=encrypt_value(body.pin) if body.pin else None,
        totp_secret_enc=encrypt_value(totp_secret) if totp_secret else None,
        zerodha_user_id=body.zerodha_user_id,
        client_id=body.client_id,
        capital=body.capital,
        auto_login=body.auto_login,
    )
    db.add(account)
    db.add(
        AuditLog(
            user_id=user.id,
            action="account.add",
            target=str(account.id),
            meta_json={"label": body.label, "broker": body.broker, "auth_mode": auth_mode},
        )
    )
    await db.flush()
    return _account_response(account)


@router.post("/{account_id}/connect", response_model=ConnectResponse)
async def connect_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, user.id, account_id)
    settings = get_settings()

    if account.broker == "zerodha":
        if account.auth_mode == "enctoken":
            raise HTTPException(
                status_code=400,
                detail="Use POST /accounts/{id}/connect-enctoken for enctoken accounts",
            )
        api_key = decrypt_value(account.api_key_enc)
        kite = KiteService(api_key, "")
        login_url = kite.login_url(settings.kite_redirect_url)
        _pending_connect[api_key] = account_id
        return ConnectResponse(login_url=login_url, account_id=account_id)

    if account.broker == "fyers":
        app_id = decrypt_value(account.api_key_enc)
        login_url = fyers_login_url(app_id, settings.fyers_redirect_url, str(account_id))
        _pending_fyers[str(account_id)] = account_id
        return ConnectResponse(login_url=login_url, account_id=account_id)

    if account.broker == "ventura" and account.auth_mode == "sso":
        app_key = decrypt_value(account.api_key_enc)
        login_url = ventura_sso_url(app_key, str(account_id))
        _pending_ventura[str(account_id)] = account_id
        return ConnectResponse(login_url=login_url, account_id=account_id)

    raise HTTPException(status_code=400, detail="Use POST /accounts/{id}/login for this broker")


@router.post("/{account_id}/login")
async def broker_login(
    account_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """TOTP/password login for Angel One, Kotak, Ventura, Zerodha enctoken."""
    account = await _get_user_account(db, user.id, account_id)

    if account.broker == "angel_one":
        api_key = decrypt_value(account.api_key_enc)
        client_code = account.client_id or ""
        pin = decrypt_value(account.pin_enc) if account.pin_enc else ""
        totp = _totp_code(account.totp_secret_enc)
        try:
            tokens = angel_login(api_key, client_code, pin, totp)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Angel login failed: {exc}") from exc
        account.access_token_enc = encrypt_value(tokens["jwt_token"])
        account.refresh_token_enc = encrypt_value(tokens.get("refresh_token", ""))
        account.token_date = date.today()

    elif account.broker == "kotak":
        consumer_key = decrypt_value(account.api_key_enc)
        mpin = decrypt_value(account.password_enc) if account.password_enc else ""
        mobile = account.zerodha_user_id or ""
        ucc = account.client_id or ""
        totp = _totp_code(account.totp_secret_enc)
        try:
            tokens = kotak_login(consumer_key, mobile, ucc, totp, mpin)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Kotak login failed: {exc}") from exc
        account.access_token_enc = encrypt_value(tokens["access_token"])
        account.client_id = tokens.get("sid", ucc)
        account.token_date = date.today()

    elif account.broker == "ventura" and account.auth_mode == "totp":
        app_key = decrypt_value(account.api_key_enc)
        secret = decrypt_value(account.api_secret_enc)
        client_id = account.client_id or ""
        totp = _totp_code(account.totp_secret_enc)
        try:
            tokens = ventura_totp_login(app_key, secret, client_id, totp)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ventura login failed: {exc}") from exc
        account.access_token_enc = encrypt_value(tokens["auth_token"])
        account.refresh_token_enc = encrypt_value(tokens.get("refresh_token", ""))
        account.token_date = date.today()

    elif account.broker == "zerodha" and account.auth_mode == "enctoken":
        return await connect_enctoken(account_id, EnctokenConnectRequest(), background_tasks, user, db)

    else:
        return await auto_login(account_id, background_tasks, user, db)

    db.add(
        AuditLog(
            user_id=user.id,
            action="account.login",
            target=str(account_id),
            meta_json={"broker": account.broker},
        )
    )
    await db.commit()
    return {"status": "connected", "account_id": str(account_id)}


@router.post("/{account_id}/connect-enctoken")
async def connect_enctoken(
    account_id: UUID,
    body: EnctokenConnectRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, user.id, account_id)
    if account.broker != "zerodha" or account.auth_mode != "enctoken":
        raise HTTPException(status_code=400, detail="Account is not configured for enctoken mode")

    user_id = account.zerodha_user_id
    enctoken: str | None = body.enctoken

    if not enctoken:
        if not account.password_enc:
            raise HTTPException(
                status_code=400,
                detail="Paste enctoken or store password for auto-login",
            )
        password = decrypt_value(account.password_enc)
        totp_secret = decrypt_value(account.totp_secret_enc) if account.totp_secret_enc else None
        if not totp_secret and not body.twofa_code:
            raise HTTPException(status_code=400, detail="TOTP secret or 2FA code required")
        service = EnctokenLoginService()
        try:
            user_id, enctoken = await service.login(
                account.zerodha_user_id or "",
                password,
                totp_secret=totp_secret,
                twofa_value=body.twofa_code,
            )
        except Exception as exc:
            logger.exception("Enctoken auto-login failed for account %s", account_id)
            raise HTTPException(status_code=502, detail=f"Enctoken login failed: {exc}") from exc

    if not user_id:
        raise HTTPException(status_code=400, detail="Zerodha user ID required")

    if enctoken:
        enctoken = normalize_enctoken(enctoken, user_id)

    try:
        broker = EnctokenService(user_id or account.zerodha_user_id or "", enctoken)
        try:
            profile = broker.profile()
            user_id = str(profile.get("user_id", user_id))
        finally:
            broker.close()
    except EnctokenSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    account.enctoken_enc = encrypt_value(enctoken)
    account.zerodha_user_id = user_id
    account.token_date = date.today()
    db.add(
        AuditLog(
            user_id=user.id,
            action="account.enctoken_connect",
            target=str(account_id),
            meta_json={"user_id": user_id},
        )
    )
    await db.commit()
    _schedule_ticker_restart(background_tasks)
    return {"status": "connected", "account_id": str(account_id), "user_id": user_id}


@router.get("/callback")
async def kite_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    request_token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    status_param = request.query_params.get("status")
    if status_param == "cancelled":
        raise HTTPException(status_code=400, detail="Login cancelled")

    api_key = request.query_params.get("api_key", "")
    account_id = _pending_connect.get(api_key)
    if not account_id:
        result = await db.execute(select(BrokerAccount))
        for acc in result.scalars().all():
            if decrypt_value(acc.api_key_enc) == api_key:
                account_id = acc.id
                break
    if not account_id:
        raise HTTPException(status_code=400, detail="Unknown account for callback")

    result = await db.execute(select(BrokerAccount).where(BrokerAccount.id == account_id))
    account = result.scalar_one()
    api_key_dec = decrypt_value(account.api_key_enc)
    api_secret = decrypt_value(account.api_secret_enc)
    kite = KiteService(api_key_dec, api_secret)
    session = kite.generate_session(request_token)
    account.access_token_enc = encrypt_value(session["access_token"])
    account.token_date = date.today()
    if session.get("user_id"):
        account.zerodha_user_id = str(session["user_id"])
    await db.commit()
    _pending_connect.pop(api_key_dec, None)
    _schedule_ticker_restart(background_tasks)
    return {"status": "connected", "account_id": str(account_id)}


@router.get("/fyers-callback")
async def fyers_callback(
    auth_code: str = Query(...),
    state: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    account_id = _pending_fyers.get(state)
    if not account_id:
        raise HTTPException(status_code=400, detail="Unknown Fyers account for callback")
    result = await db.execute(select(BrokerAccount).where(BrokerAccount.id == account_id))
    account = result.scalar_one()
    app_id = decrypt_value(account.api_key_enc)
    secret = decrypt_value(account.api_secret_enc)
    token = fyers_generate_token(app_id, secret, auth_code)
    account.access_token_enc = encrypt_value(token)
    account.token_date = date.today()
    await db.commit()
    _pending_fyers.pop(state, None)
    return {"status": "connected", "account_id": str(account_id)}


@router.get("/ventura-callback")
async def ventura_callback(
    request_token: str = Query(...),
    state: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    account_id = _pending_ventura.get(state)
    if not account_id:
        raise HTTPException(status_code=400, detail="Unknown Ventura account for callback")
    result = await db.execute(select(BrokerAccount).where(BrokerAccount.id == account_id))
    account = result.scalar_one()
    app_key = decrypt_value(account.api_key_enc)
    secret = decrypt_value(account.api_secret_enc)
    tokens = ventura_generate_token(app_key, secret, request_token)
    account.access_token_enc = encrypt_value(tokens["auth_token"])
    account.refresh_token_enc = encrypt_value(tokens.get("refresh_token", ""))
    if tokens.get("client_id"):
        account.client_id = tokens["client_id"]
    account.token_date = date.today()
    await db.commit()
    _pending_ventura.pop(state, None)
    return {"status": "connected", "account_id": str(account_id)}


@router.post("/{account_id}/auto-login")
async def auto_login(
    account_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, user.id, account_id)

    if account.broker != "zerodha":
        return await broker_login(account_id, user, db)

    if not account.zerodha_user_id:
        raise HTTPException(status_code=400, detail="Zerodha user ID required for auto-login")

    if account.auth_mode == "enctoken":
        return await connect_enctoken(account_id, EnctokenConnectRequest(), background_tasks, user, db)

    if not account.totp_secret_enc:
        raise HTTPException(status_code=400, detail="TOTP secret required for Kite Connect auto-login")

    from app.broker.totp_login import TotpLoginService

    api_key = decrypt_value(account.api_key_enc)
    api_secret = decrypt_value(account.api_secret_enc)
    totp_secret = decrypt_value(account.totp_secret_enc)
    settings = get_settings()
    service = TotpLoginService(api_key, api_secret, totp_secret, settings.kite_redirect_url)
    try:
        access_token = await service.login(account.zerodha_user_id)
    except Exception as exc:
        logger.exception("Auto-login failed for account %s", account_id)
        raise HTTPException(status_code=502, detail=f"Auto-login failed: {exc}") from exc

    account.access_token_enc = encrypt_value(access_token)
    account.token_date = date.today()
    db.add(
        AuditLog(
            user_id=user.id,
            action="account.auto_login",
            target=str(account_id),
            meta_json={"auth_mode": account.auth_mode},
        )
    )
    await db.commit()
    _schedule_ticker_restart(background_tasks)
    return {"status": "connected", "account_id": str(account_id)}


@router.patch("/{account_id}", response_model=BrokerAccountResponse)
async def update_account(
    account_id: UUID,
    body: BrokerAccountUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, user.id, account_id)
    if body.label is not None:
        account.label = body.label
    if body.capital is not None:
        account.capital = body.capital
    if body.zerodha_user_id is not None:
        account.zerodha_user_id = body.zerodha_user_id
    if body.client_id is not None:
        account.client_id = body.client_id
    if body.zerodha_password:
        account.password_enc = encrypt_value(body.zerodha_password)
    if body.pin:
        account.pin_enc = encrypt_value(body.pin)
    if body.totp_secret:
        account.totp_secret_enc = encrypt_value(normalize_totp_secret(body.totp_secret))
    if body.api_key:
        account.api_key_enc = encrypt_value(body.api_key)
    if body.api_secret:
        account.api_secret_enc = encrypt_value(body.api_secret)
    if body.auto_login is not None:
        account.auto_login = body.auto_login
    if body.enabled is not None:
        account.enabled = body.enabled

    db.add(
        AuditLog(
            user_id=user.id,
            action="account.update",
            target=str(account_id),
            meta_json={"label": account.label},
        )
    )
    await db.commit()
    await db.refresh(account)
    return _account_response(account)


@router.get("/{account_id}/live-info", response_model=BrokerLiveInfoResponse)
async def get_account_live_info(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_user_account(db, user.id, account_id)
    if not account_session_active(account):
        raise HTTPException(status_code=400, detail="Account session not active — reconnect first")

    from app.broker.broker_info import fetch_live_info

    broker = None
    try:
        broker = get_broker_for_account(account)
        info = fetch_live_info(broker)
    except EnctokenSessionError as exc:
        account.enctoken_enc = None
        account.token_date = None
        await db.commit()
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to fetch live info for account %s", account_id)
        raise HTTPException(status_code=502, detail=f"Failed to fetch broker info: {exc}") from exc
    finally:
        if broker is not None:
            broker.close()

    return BrokerLiveInfoResponse(**info)


async def _get_user_account(db: AsyncSession, user_id: UUID, account_id: UUID) -> BrokerAccount:
    result = await db.execute(
        select(BrokerAccount).where(
            BrokerAccount.id == account_id,
            BrokerAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
