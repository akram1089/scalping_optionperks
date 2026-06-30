"""Broker session helpers — unified access for Kite Connect and enctoken modes."""

from datetime import date

from app.auth.crypto import decrypt_value
from app.broker.enctoken_client import EnctokenService
from app.broker.kite_client import KiteService
from app.models import BrokerAccount


def account_session_active(account: BrokerAccount) -> bool:
    today = date.today()
    if not account.token_date or account.token_date < today:
        return False
    if account.auth_mode == "enctoken":
        return bool(account.enctoken_enc)
    return bool(account.access_token_enc)


def get_broker_for_account(account: BrokerAccount) -> KiteService | EnctokenService:
    if account.auth_mode == "enctoken":
        if not account.enctoken_enc or not account.zerodha_user_id:
            raise RuntimeError("No active enctoken session for account")
        enctoken = decrypt_value(account.enctoken_enc)
        return EnctokenService(account.zerodha_user_id, enctoken)

    api_key = decrypt_value(account.api_key_enc)
    api_secret = decrypt_value(account.api_secret_enc)
    token = decrypt_value(account.access_token_enc) if account.access_token_enc else None
    if not token:
        raise RuntimeError("No active Kite Connect session for account")
    return KiteService(api_key, api_secret, token)
