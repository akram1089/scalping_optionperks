"""Canonical Zerodha quote keys for index LTP (exchange:tradingsymbol)."""

# Dashboard label → quote API keys to try in order (first match wins)
INDEX_LTP_ALIASES: dict[str, list[str]] = {
    "NIFTY 50": ["NSE:NIFTY 50", "NSE:NIFTY"],
    "BANK NIFTY": ["NSE:NIFTY BANK", "NSE:BANKNIFTY"],
    "SENSEX": ["BSE:SENSEX"],
}

INDEX_DISPLAY_SYMBOLS = tuple(INDEX_LTP_ALIASES.keys())
