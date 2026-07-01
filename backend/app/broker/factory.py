"""Broker factory — instantiate the correct adapter for an account."""

from datetime import date

from app.auth.crypto import decrypt_value
from app.broker.angel.adapter import AngelOneBroker
from app.broker.base import BrokerService
from app.broker.enctoken_client import EnctokenService
from app.broker.fyers.adapter import FyersBroker
from app.broker.kite_client import KiteService
from app.broker.kotak.adapter import KotakBroker
from app.broker.ventura.adapter import VenturaBroker
from app.broker.zerodha.adapter import ZerodhaBroker
from app.models import BrokerAccount


def account_session_active(account: BrokerAccount) -> bool:
    today = date.today()
    if not account.token_date or account.token_date < today:
        return False
    broker = account.broker or "zerodha"
    if broker == "zerodha" and account.auth_mode == "enctoken":
        return bool(account.enctoken_enc)
    return bool(account.access_token_enc)


def get_broker_for_account(account: BrokerAccount) -> BrokerService:
    broker = account.broker or "zerodha"

    if broker == "zerodha":
        if account.auth_mode == "enctoken":
            if not account.enctoken_enc or not account.zerodha_user_id:
                raise RuntimeError("No active enctoken session for account")
            enctoken = decrypt_value(account.enctoken_enc)
            return ZerodhaBroker(EnctokenService(account.zerodha_user_id, enctoken))
        api_key = decrypt_value(account.api_key_enc)
        api_secret = decrypt_value(account.api_secret_enc)
        token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
        if not token:
            raise RuntimeError("No active Kite Connect session for account")
        return ZerodhaBroker(KiteService(api_key, api_secret, token))

    if broker == "angel_one":
        api_key = decrypt_value(account.api_key_enc)
        token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
        if not token:
            raise RuntimeError("No active Angel One session for account")
        feed = decrypt_value(account.refresh_token_enc) if account.refresh_token_enc else ""
        return AngelOneBroker(api_key, token, feed)

    if broker == "fyers":
        app_id = decrypt_value(account.api_key_enc)
        token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
        if not token:
            raise RuntimeError("No active Fyers session for account")
        return FyersBroker(app_id, token)

    if broker == "kotak":
        token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
        sid = account.client_id or account.zerodha_user_id or ""
        consumer_key = decrypt_value(account.api_key_enc)
        if not token:
            raise RuntimeError("No active Kotak session for account")
        return KotakBroker(token, sid, consumer_key)

    if broker == "ventura":
        app_key = decrypt_value(account.api_key_enc)
        token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
        client_id = account.client_id or account.zerodha_user_id or ""
        if not token:
            raise RuntimeError("No active Ventura session for account")
        return VenturaBroker(app_key, token, client_id)

    raise RuntimeError(f"Unsupported broker: {broker}")
