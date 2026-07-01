"""Fetch live broker snapshot — profile, margins, positions."""

from typing import Any

from app.broker.base import BrokerService


def _dec(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _equity_margins(margins: dict[str, Any]) -> dict[str, float]:
    equity = margins.get("equity") or margins
    available = equity.get("available") or {}
    utilised = equity.get("utilised") or {}
    return {
        "net": _dec(equity.get("net")),
        "available_cash": _dec(available.get("live_balance") or available.get("cash")),
        "opening_balance": _dec(available.get("opening_balance")),
        "collateral": _dec(available.get("collateral")),
        "utilised_debits": _dec(utilised.get("debits")),
        "m2m_unrealised": _dec(utilised.get("m2m_unrealised")),
        "m2m_realised": _dec(utilised.get("m2m_realised")),
    }


def _position_summary(positions: dict[str, Any]) -> dict[str, int | float]:
    net = positions.get("net") or []
    day = positions.get("day") or []
    open_net = [p for p in net if int(p.get("quantity") or 0) != 0]
    pnl = sum(_dec(p.get("pnl")) for p in open_net)
    return {
        "open_positions": len(open_net),
        "day_trades": len([p for p in day if int(p.get("quantity") or 0) != 0]),
        "unrealised_pnl": round(pnl, 2),
    }


def fetch_live_info(broker: BrokerService) -> dict[str, Any]:
    profile = broker.profile()
    margins_raw = broker.margins()
    equity = _equity_margins(margins_raw)
    holdings = broker.holdings()
    positions = broker.positions()
    pos_summary = _position_summary(positions)

    return {
        "user_id": profile.get("user_id") or profile.get("user_name"),
        "user_name": profile.get("user_name"),
        "email": profile.get("email"),
        "broker": profile.get("broker") or getattr(broker, "broker_slug", None),
        "exchanges": profile.get("exchanges") or [],
        "products": profile.get("products") or [],
        "order_types": profile.get("order_types") or [],
        "margins": equity,
        "holdings_count": len(holdings),
        "holdings_value": round(
            sum(_dec(h.get("last_price", 0)) * _dec(h.get("quantity", 0)) for h in holdings), 2
        ),
        "positions": pos_summary,
    }
