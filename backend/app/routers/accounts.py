import logging

from datetime import date

from uuid import UUID



from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession



from app.auth.crypto import decrypt_value, encrypt_value

from app.auth.jwt import get_current_user

from app.broker.session import account_session_active, get_broker_for_account

from app.config import get_settings

from app.db import get_db

from app.models import AuditLog, BrokerAccount, User

from app.schemas import (
    BrokerAccountCreate,
    BrokerAccountResponse,
    BrokerAccountUpdate,
    BrokerLiveInfoResponse,
    ConnectResponse,
    EnctokenConnectRequest,
)

from app.broker.enctoken_login import normalize_totp_secret
from app.broker.kite_client import KiteService



logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])



_pending_connect: dict[str, UUID] = {}





def _account_response(account: BrokerAccount) -> BrokerAccountResponse:

    return BrokerAccountResponse(

        id=account.id,

        label=account.label,

        broker=account.broker,

        auth_mode=account.auth_mode,

        zerodha_user_id=account.zerodha_user_id,

        capital=account.capital,

        auto_login=account.auto_login,

        enabled=account.enabled,
        totp_configured=bool(account.totp_secret_enc),
        token_date=account.token_date,

        session_active=account_session_active(account),

    )





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

    if body.auto_login and not body.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP secret required when auto-login is enabled")

    totp_secret = normalize_totp_secret(body.totp_secret) if body.totp_secret else None

    account = BrokerAccount(

        user_id=user.id,

        label=body.label,

        auth_mode=body.auth_mode,

        api_key_enc=encrypt_value(body.api_key or ""),

        api_secret_enc=encrypt_value(body.api_secret or ""),

        password_enc=encrypt_value(body.zerodha_password) if body.zerodha_password else None,

        totp_secret_enc=encrypt_value(totp_secret) if totp_secret else None,

        zerodha_user_id=body.zerodha_user_id,

        capital=body.capital,

        auto_login=body.auto_login,

    )

    db.add(account)

    db.add(

        AuditLog(

            user_id=user.id,

            action="account.add",

            target=str(account.id),

            meta_json={"label": body.label, "auth_mode": body.auth_mode},

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

    if account.auth_mode == "enctoken":

        raise HTTPException(

            status_code=400,

            detail="Use POST /accounts/{id}/connect-enctoken for enctoken accounts",

        )

    api_key = decrypt_value(account.api_key_enc)

    settings = get_settings()

    kite = KiteService(api_key, "")

    login_url = kite.login_url(settings.kite_redirect_url)

    _pending_connect[api_key] = account_id

    return ConnectResponse(login_url=login_url, account_id=account_id)





@router.post("/{account_id}/connect-enctoken")

async def connect_enctoken(

    account_id: UUID,

    body: EnctokenConnectRequest,

    user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    """Connect via enctoken — paste from browser cookies or auto-login with stored creds."""

    account = await _get_user_account(db, user.id, account_id)

    if account.auth_mode != "enctoken":

        raise HTTPException(status_code=400, detail="Account is not configured for enctoken mode")



    user_id = account.zerodha_user_id

    enctoken: str | None = body.enctoken



    if not enctoken:

        if not account.password_enc:

            raise HTTPException(

                status_code=400,

                detail="Paste enctoken from browser (F12 → Application → Cookies → enctoken) or store password for auto-login",

            )

        from app.broker.enctoken_login import EnctokenLoginService



        password = decrypt_value(account.password_enc)

        totp_secret = decrypt_value(account.totp_secret_enc) if account.totp_secret_enc else None

        if not totp_secret and not body.twofa_code:

            raise HTTPException(

                status_code=400,

                detail="TOTP secret or one-time 2FA code required for auto-login",

            )

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



    from app.broker.enctoken_client import EnctokenService, EnctokenSessionError, normalize_enctoken

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
    except Exception as exc:
        logger.exception("Enctoken validation failed for account %s", account_id)
        raise HTTPException(status_code=400, detail=f"Invalid enctoken: {exc}") from exc



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

    return {"status": "connected", "account_id": str(account_id), "user_id": user_id}





@router.get("/callback")

async def kite_callback(

    request: Request,

    request_token: str = Query(...),

    db: AsyncSession = Depends(get_db),

):

    """Public callback — Kite redirects here after manual login."""

    status_param = request.query_params.get("status")

    if status_param == "cancelled":

        raise HTTPException(status_code=400, detail="Login cancelled")



    api_key = request.query_params.get("api_key", "")

    account_id = _pending_connect.get(api_key)

    if not account_id:

        result = await db.execute(select(BrokerAccount))

        accounts = result.scalars().all()

        for acc in accounts:

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

    return {"status": "connected", "account_id": str(account_id)}





@router.post("/{account_id}/auto-login")

async def auto_login(

    account_id: UUID,

    user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    account = await _get_user_account(db, user.id, account_id)

    if not account.zerodha_user_id:
        raise HTTPException(status_code=400, detail="Zerodha user ID required for auto-login")

    if account.auth_mode == "enctoken":

        from app.broker.enctoken_login import EnctokenLoginService



        if not account.password_enc:

            raise HTTPException(status_code=400, detail="Password required for enctoken auto-login")

        if not account.totp_secret_enc:

            raise HTTPException(status_code=400, detail="TOTP secret required for enctoken auto-login")



        password = decrypt_value(account.password_enc)

        totp_secret = decrypt_value(account.totp_secret_enc)

        service = EnctokenLoginService()

        try:

            user_id, enctoken = await service.login(account.zerodha_user_id, password, totp_secret)

        except Exception as exc:

            logger.exception("Enctoken auto-login failed for account %s", account_id)

            raise HTTPException(status_code=502, detail=f"Auto-login failed: {exc}") from exc



        account.enctoken_enc = encrypt_value(enctoken)

        account.zerodha_user_id = user_id

        account.token_date = date.today()

    else:

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
    if body.zerodha_password:
        account.password_enc = encrypt_value(body.zerodha_password)
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
    from app.broker.enctoken_client import EnctokenService, EnctokenSessionError

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
        if isinstance(broker, EnctokenService):
            broker.close()

    return BrokerLiveInfoResponse(**info)




async def _get_user_account(db: AsyncSession, user_id: UUID, account_id: UUID) -> BrokerAccount:

    result = await db.execute(

        select(BrokerAccount).where(

            BrokerAccount.id == account_id, BrokerAccount.user_id == user_id

        )

    )

    account = result.scalar_one_or_none()

    if not account:

        raise HTTPException(status_code=404, detail="Account not found")

    return account

