"""Position sizing based on risk percentage and stop distance."""

from decimal import Decimal, ROUND_DOWN
from math import floor


def calculate_qty(
    capital: Decimal,
    risk_pct: Decimal,
    entry_price: float,
    stop_price: float,
    lot_size: int = 1,
) -> int:
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        return 0
    risk_amount = float(capital) * (float(risk_pct) / 100.0)
    raw_qty = risk_amount / stop_distance
    qty = int(floor(raw_qty))
    if lot_size > 1:
        qty = (qty // lot_size) * lot_size
    return max(qty, 0)


def stop_from_atr(entry: float, atr: float, side: str, multiplier: float = 1.5) -> float:
    if side == "BUY":
        return entry - atr * multiplier
    return entry + atr * multiplier


def target_from_rr(entry: float, stop: float, side: str, rr: float) -> float:
    risk = abs(entry - stop)
    if side == "BUY":
        return entry + risk * rr
    return entry - risk * rr
