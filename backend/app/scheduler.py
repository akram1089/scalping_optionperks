import logging
from contextlib import asynccontextmanager
from datetime import date

import pyotp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.broker.angel.adapter import angel_login
from app.broker.enctoken_login import EnctokenLoginService, normalize_totp_secret
from app.broker.instruments_sync import run_instrument_sync_job
from app.broker.kotak.adapter import kotak_login
from app.config import get_settings
from app.db import async_session
from app.models import BrokerAccount, GlobalState, Strategy

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _login_zerodha(account: BrokerAccount) -> None:
    from app.auth.crypto import decrypt_value, encrypt_value
    from app.broker.totp_login import TotpLoginService

    if account.auth_mode == "enctoken":
        if not account.password_enc or not account.totp_secret_enc:
            raise RuntimeError("password + TOTP required")
        service = EnctokenLoginService()
        user_id, enctoken = await service.login(
            account.zerodha_user_id or "",
            decrypt_value(account.password_enc),
            decrypt_value(account.totp_secret_enc),
        )
        account.enctoken_enc = encrypt_value(enctoken)
        account.zerodha_user_id = user_id
    else:
        if not account.totp_secret_enc:
            raise RuntimeError("TOTP required")
        settings = get_settings()
        service = TotpLoginService(
            decrypt_value(account.api_key_enc),
            decrypt_value(account.api_secret_enc),
            decrypt_value(account.totp_secret_enc),
            settings.kite_redirect_url,
        )
        account.access_token_enc = encrypt_value(await service.login(account.zerodha_user_id or ""))


async def _login_angel(account: BrokerAccount) -> None:
    from app.auth.crypto import decrypt_value, encrypt_value

    totp = pyotp.TOTP(normalize_totp_secret(decrypt_value(account.totp_secret_enc))).now()
    tokens = angel_login(
        decrypt_value(account.api_key_enc),
        account.client_id or "",
        decrypt_value(account.pin_enc) if account.pin_enc else "",
        totp,
    )
    account.access_token_enc = encrypt_value(tokens["jwt_token"])
    account.refresh_token_enc = encrypt_value(tokens.get("refresh_token", ""))


async def _login_kotak(account: BrokerAccount) -> None:
    from app.auth.crypto import decrypt_value, encrypt_value

    totp = pyotp.TOTP(normalize_totp_secret(decrypt_value(account.totp_secret_enc))).now()
    tokens = kotak_login(
        decrypt_value(account.api_key_enc),
        account.zerodha_user_id or "",
        account.client_id or "",
        totp,
        decrypt_value(account.password_enc) if account.password_enc else "",
    )
    account.access_token_enc = encrypt_value(tokens["access_token"])
    account.client_id = tokens.get("sid", account.client_id)


async def morning_login_job() -> None:
    logger.info("Morning login job started")
    async with async_session() as db:
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.enabled.is_(True), BrokerAccount.auto_login.is_(True)
            )
        )
        accounts = result.scalars().all()
        for account in accounts:
            if account.token_date and account.token_date >= date.today():
                continue
            try:
                broker = account.broker or "zerodha"
                if broker == "zerodha":
                    if not account.zerodha_user_id:
                        logger.warning("Account %s needs manual login", account.id)
                        continue
                    await _login_zerodha(account)
                elif broker == "angel_one":
                    await _login_angel(account)
                elif broker == "kotak":
                    await _login_kotak(account)
                else:
                    logger.warning("Auto-login not supported for broker %s", broker)
                    continue
                account.token_date = date.today()
                logger.info("Auto-login success for %s", account.label)
            except Exception:
                logger.exception("Auto-login failed for %s", account.label)
        await db.commit()


async def eod_squareoff_job() -> None:
    logger.info("EOD square-off job started")
    from app.engine.manage import TradeManager

    async with async_session() as db:
        manager = TradeManager(db)
        await manager.eod_square_off()
        await db.commit()


async def resume_running_strategies() -> None:
    from app.engine.runtime import strategy_runtime

    async with async_session() as db:
        result = await db.execute(select(Strategy).where(Strategy.running.is_(True)))
        for strategy in result.scalars().all():
            await strategy_runtime.start_strategy(strategy.id)


async def ensure_global_state() -> None:
    async with async_session() as db:
        result = await db.execute(select(GlobalState).where(GlobalState.id == 1))
        if not result.scalar_one_or_none():
            db.add(GlobalState(id=1, kill_switch=False))
            await db.commit()


def setup_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    sync_hour, sync_minute = _parse_time(settings.instrument_sync_time, default=(8, 50))
    login_hour, login_minute = _parse_time(settings.market_open_login_time, default=(8, 45))
    eod_hour, eod_minute = _parse_time(settings.eod_squareoff_time, default=(15, 20))

    scheduler.add_job(
        morning_login_job,
        CronTrigger(hour=login_hour, minute=login_minute, timezone=settings.timezone),
        id="morning_login",
    )
    scheduler.add_job(
        run_instrument_sync_job,
        CronTrigger(hour=sync_hour, minute=sync_minute, timezone=settings.timezone),
        id="instrument_sync",
    )
    scheduler.add_job(
        eod_squareoff_job,
        CronTrigger(hour=eod_hour, minute=eod_minute, timezone=settings.timezone),
        id="eod_squareoff",
    )
    return scheduler


def _parse_time(value: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        hour, minute = value.strip().split(":")
        return int(hour), int(minute)
    except (ValueError, AttributeError):
        return default
