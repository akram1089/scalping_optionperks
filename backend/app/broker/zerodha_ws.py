"""KiteTicker session credentials for Zerodha OAuth and enctoken."""

from app.auth.crypto import decrypt_value
from app.broker.enctoken_client import normalize_enctoken
from app.config import get_settings
from app.models import BrokerAccount


def zerodha_ticker_credentials(account: BrokerAccount) -> tuple[str, str] | None:
    """Return (api_key, access_token) for KiteTicker.

    Enctoken sessions cannot use REST quote/ltp (Zerodha returns 400). WebSocket
    auth uses: ``{enctoken}&user_id={zerodha_user_id}`` per community KiteTicker usage.
    """
    settings = get_settings()
    api_key = (
        decrypt_value(account.api_key_enc) if account.api_key_enc else settings.kite_ws_api_key
    )

    if account.auth_mode == "enctoken":
        if not account.enctoken_enc or not account.zerodha_user_id:
            return None
        enctoken = normalize_enctoken(
            decrypt_value(account.enctoken_enc), account.zerodha_user_id
        )
        ws_token = f"{enctoken}&user_id={account.zerodha_user_id}"
        return api_key, ws_token

    if not account.access_token_enc:
        return None
    access_token = decrypt_value(account.access_token_enc)
    if not api_key:
        return None
    return api_key, access_token
