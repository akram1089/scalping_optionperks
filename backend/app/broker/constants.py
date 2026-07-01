"""Broker slugs and normalized trading constants."""

from typing import Literal

BrokerSlug = Literal["zerodha", "angel_one", "fyers", "kotak", "ventura"]

SUPPORTED_BROKERS: list[BrokerSlug] = [
    "zerodha",
    "angel_one",
    "fyers",
    "kotak",
    "ventura",
]

BROKER_LABELS: dict[str, str] = {
    "zerodha": "Zerodha",
    "angel_one": "Angel One",
    "fyers": "Fyers",
    "kotak": "Kotak",
    "ventura": "Ventura",
}

# Normalized product / order types used by execution layer
PRODUCT_MIS = "MIS"
PRODUCT_NRML = "NRML"
ORDER_LIMIT = "LIMIT"
ORDER_MARKET = "MARKET"
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
