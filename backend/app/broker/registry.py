"""Broker registry — metadata for supported brokers and credential requirements."""

from typing import Any

from app.broker.constants import BROKER_LABELS, SUPPORTED_BROKERS

BROKER_CONFIG: dict[str, dict[str, Any]] = {
    "zerodha": {
        "label": BROKER_LABELS["zerodha"],
        "auth_modes": ["kite_connect", "enctoken"],
        "required_fields": {
            "kite_connect": ["api_key", "api_secret"],
            "enctoken": ["zerodha_user_id", "zerodha_password", "totp_secret"],
        },
        "connect_type": "oauth_or_enctoken",
    },
    "angel_one": {
        "label": BROKER_LABELS["angel_one"],
        "auth_modes": ["smartapi"],
        "required_fields": {
            "smartapi": ["api_key", "client_id", "pin", "totp_secret"],
        },
        "connect_type": "totp_login",
    },
    "fyers": {
        "label": BROKER_LABELS["fyers"],
        "auth_modes": ["oauth"],
        "required_fields": {
            "oauth": ["api_key", "api_secret"],
        },
        "connect_type": "oauth",
    },
    "kotak": {
        "label": BROKER_LABELS["kotak"],
        "auth_modes": ["totp"],
        "required_fields": {
            "totp": ["api_key", "client_id", "zerodha_password", "totp_secret"],
        },
        "connect_type": "totp_login",
    },
    "ventura": {
        "label": BROKER_LABELS["ventura"],
        "auth_modes": ["sso", "totp"],
        "required_fields": {
            "sso": ["api_key", "api_secret"],
            "totp": ["api_key", "api_secret", "client_id", "totp_secret"],
        },
        "connect_type": "oauth_or_totp",
    },
}


def list_brokers() -> list[dict[str, Any]]:
    return [
        {"slug": slug, **BROKER_CONFIG[slug]}
        for slug in SUPPORTED_BROKERS
    ]
