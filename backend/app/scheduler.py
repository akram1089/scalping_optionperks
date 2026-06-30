import logging
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.broker.instruments_sync import run_instrument_sync_job
from app.config import get_settings
from app.db import async_session
from app.models import BrokerAccount, GlobalState, Strategy

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def morning_login_job() -> None:
    logger.info("Morning login job started")
    async with async_session() as db:
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.enabled.is_(True), BrokerAccount.auto_login.is_(True))
        )
        accounts = result.scalars().all()
        for account in accounts:
            if account.token_date and account.token_date >= date.today():
                continue
            if not account.zerodha_user_id:
                logger.warning("Account %s needs manual login", account.id)
                continue
            try:
                from app.auth.crypto import decrypt_value, encrypt_value

                if account.auth_mode == "enctoken":
                    if not account.password_enc or not account.totp_secret_enc:
                        logger.warning("Account %s needs password + TOTP for enctoken auto-login", account.id)
                        continue
                    from app.broker.enctoken_login import EnctokenLoginService

                    service = EnctokenLoginService()
                    user_id, enctoken = await service.login(
                        account.zerodha_user_id,
                        decrypt_value(account.password_enc),
                        decrypt_value(account.totp_secret_enc),
                    )
                    account.enctoken_enc = encrypt_value(enctoken)
                    account.zerodha_user_id = user_id
                else:
                    if not account.totp_secret_enc:
                        logger.warning("Account %s needs TOTP for Kite Connect auto-login", account.id)
                        continue
                    from app.broker.totp_login import TotpLoginService

                    settings = get_settings()
                    service = TotpLoginService(
                        decrypt_value(account.api_key_enc),
                        decrypt_value(account.api_secret_enc),
                        decrypt_value(account.totp_secret_enc),
                        settings.kite_redirect_url,
                    )
                    token = await service.login(account.zerodha_user_id)
                    account.access_token_enc = encrypt_value(token)
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
