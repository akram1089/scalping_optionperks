"""Kotak Neo Trade API adapter."""

import logging
from typing import Any

import httpx

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY, SIDE_SELL

logger = logging.getLogger(__name__)

_BASE = "https://gw-napi.kotaksecurities.com"
_EXCHANGE_SEG = {"NSE": "nse_cm", "NFO": "nse_fo", "BSE": "bse_cm"}
_PRODUCT_MAP = {PRODUCT_MIS: "MIS", "NRML": "NRML"}


class KotakBroker:
    broker_slug = "kotak"

    def __init__(self, access_token: str, sid: str, consumer_key: str):
        self.access_token = access_token
        self.sid = sid
        self.consumer_key = consumer_key
        self._client = httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Sid": self.sid,
            "neo-fin-key": "neotradeapi",
        }

    def _get(self, path: str) -> Any:
        r = self._client.get(f"{_BASE}{path}", headers=self._headers())
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> Any:
        r = self._client.post(f"{_BASE}{path}", json=body, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("stat") == "Not_Ok":
            raise RuntimeError(data.get("emsg", str(data)))
        return data

    def close(self) -> None:
        self._client.close()

    def profile(self) -> dict[str, Any]:
        return {
            "user_id": self.sid,
            "user_name": None,
            "email": None,
            "broker": "KOTAK",
            "exchanges": list(_EXCHANGE_SEG.keys()),
            "products": ["MIS", "NRML"],
            "order_types": ["LIMIT", "MARKET"],
        }

    def margins(self) -> dict[str, Any]:
        try:
            m = self._get("/Orders/2.0/quick/user/check-margin")
            equity = {
                "net": float(m.get("Net", 0) or 0),
                "available": {
                    "live_balance": float(m.get("AvailableMargin", 0) or 0),
                    "opening_balance": float(m.get("AvailableMargin", 0) or 0),
                    "collateral": 0.0,
                },
                "utilised": {"debits": 0.0, "m2m_unrealised": 0.0, "m2m_realised": 0.0},
            }
        except Exception:
            equity = {
                "net": 0.0,
                "available": {"live_balance": 0.0, "opening_balance": 0.0, "collateral": 0.0},
                "utilised": {"debits": 0.0, "m2m_unrealised": 0.0, "m2m_realised": 0.0},
            }
        return {"equity": equity}

    def holdings(self) -> list[dict[str, Any]]:
        try:
            return self._get("/Portfolio/1.0/portfolio/v1/holdings").get("data", [])
        except Exception:
            return []

    def positions(self) -> dict[str, Any]:
        try:
            raw = self._get("/Orders/2.0/quick/user/positions").get("data", [])
        except Exception:
            raw = []
        net = [
            {
                "tradingsymbol": p.get("trdSym", p.get("tradingSymbol", "")),
                "quantity": int(p.get("flBuyQty", 0) or 0) - int(p.get("flSellQty", 0) or 0),
                "pnl": float(p.get("unrealizedMTM", 0) or 0),
            }
            for p in raw
        ]
        return {"net": net, "day": net}

    def orders(self) -> list[dict[str, Any]]:
        try:
            return self._get("/Orders/2.0/quick/user/orders").get("data", [])
        except Exception:
            return []

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        return {}

    def instruments(self, exchange: str = "NSE") -> list[dict[str, Any]]:
        return []

    def historical_data(
        self,
        exchange: str,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str,
    ) -> list[dict[str, Any]]:
        return []

    def place_order(
        self,
        *,
        exchange: str,
        symbol: str,
        side: str,
        qty: int,
        product: str,
        order_type: str,
        price: float | None = None,
    ) -> str:
        body = {
            "am": "NO",
            "dq": "0",
            "es": _EXCHANGE_SEG.get(exchange, "nse_cm"),
            "mp": "0",
            "pc": _PRODUCT_MAP.get(product, "MIS"),
            "pf": "N",
            "pr": str(price or 0),
            "pt": "L" if order_type == ORDER_LIMIT else "MKT",
            "qt": str(qty),
            "rt": "DAY",
            "tp": "0",
            "ts": symbol,
            "tt": "B" if side == SIDE_BUY else "S",
        }
        data = self._post("/Orders/2.0/quick/order/rule/ms/place", body)
        return str(data.get("nOrdNo", data.get("orderId", data)))

    def cancel_order(self, order_id: str) -> str:
        self._post("/Orders/2.0/quick/order/cancel", {"on": order_id})
        return order_id


def kotak_login(
    consumer_key: str,
    mobile: str,
    ucc: str,
    totp: str,
    mpin: str,
) -> dict[str, str]:
    """Login to Kotak Neo API via TOTP flow."""
    try:
        from neo_api_client import NeoAPI  # type: ignore[import-untyped]

        client = NeoAPI(environment="prod", access_token=None, neo_fin_key=None, consumer_key=consumer_key)
        client.login(mobilenumber=mobile, password=mpin)
        client.session_2fa(OTP=totp)
        return {
            "access_token": client.configuration.access_token or "",
            "sid": getattr(client, "sid", ucc) or ucc,
        }
    except ImportError:
        pass

    # Fallback REST login
    with httpx.Client(timeout=30) as http:
        r = http.post(
            f"{_BASE}/login/1.0/login/v2/validate",
            json={"mobileNumber": mobile, "password": mpin},
            headers={"Authorization": consumer_key, "neo-fin-key": "neotradeapi"},
        )
        r.raise_for_status()
        data = r.json()
        sid = data.get("data", {}).get("sid", ucc)
        r2 = http.post(
            f"{_BASE}/login/1.0/login/v2/validate",
            json={"otp": totp},
            headers={"Authorization": consumer_key, "Sid": sid, "neo-fin-key": "neotradeapi"},
        )
        r2.raise_for_status()
        token_data = r2.json().get("data", {})
        return {
            "access_token": token_data.get("token", ""),
            "sid": sid,
        }
