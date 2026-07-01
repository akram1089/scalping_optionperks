"""Ventura EaseAPI adapter."""

import hashlib
import logging
from typing import Any

import httpx

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY, SIDE_SELL

logger = logging.getLogger(__name__)

_BASE = "https://easeapi.venturasecurities.com"


class VenturaBroker:
    broker_slug = "ventura"

    def __init__(self, app_key: str, auth_token: str, client_id: str):
        self.app_key = app_key
        self.auth_token = auth_token
        self.client_id = client_id
        self._client = httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-App-Key": self.app_key,
        }

    def _get(self, path: str) -> Any:
        r = self._client.get(f"{_BASE}{path}", headers=self._headers())
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> Any:
        r = self._client.post(f"{_BASE}{path}", json=body, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("status") == "error":
            raise RuntimeError(data.get("message", str(data)))
        return data.get("data", data)

    def close(self) -> None:
        self._client.close()

    def profile(self) -> dict[str, Any]:
        try:
            p = self._get(f"/user/v1/profile?client_id={self.client_id}")
        except Exception:
            p = {}
        return {
            "user_id": self.client_id,
            "user_name": p.get("name"),
            "email": p.get("email"),
            "broker": "VENTURA",
            "exchanges": p.get("exchanges", ["NSE", "NFO"]),
            "products": [],
            "order_types": [],
        }

    def margins(self) -> dict[str, Any]:
        try:
            m = self._get(f"/funds/v1/margins?client_id={self.client_id}")
        except Exception:
            m = {}
        equity = {
            "net": float(m.get("net", 0) or 0),
            "available": {
                "live_balance": float(m.get("available", 0) or 0),
                "opening_balance": float(m.get("available", 0) or 0),
                "collateral": 0.0,
            },
            "utilised": {"debits": 0.0, "m2m_unrealised": 0.0, "m2m_realised": 0.0},
        }
        return {"equity": equity}

    def holdings(self) -> list[dict[str, Any]]:
        try:
            return self._get(f"/portfolio/v1/holdings?client_id={self.client_id}").get("holdings", [])
        except Exception:
            return []

    def positions(self) -> dict[str, Any]:
        try:
            raw = self._get(f"/portfolio/v1/positions?client_id={self.client_id}").get("positions", [])
        except Exception:
            raw = []
        net = [
            {
                "tradingsymbol": p.get("symbol", ""),
                "quantity": int(p.get("quantity", 0) or 0),
                "pnl": float(p.get("pnl", 0) or 0),
            }
            for p in raw
        ]
        return {"net": net, "day": net}

    def orders(self) -> list[dict[str, Any]]:
        try:
            return self._get(f"/trade/v1/orders?client_id={self.client_id}").get("orders", [])
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
        try:
            body = {
                "exchange": exchange,
                "symbol": symbol,
                "from": from_date[:10],
                "to": to_date[:10],
                "interval": interval,
            }
            candles = self._post("/market/v1/candles", body)
            if isinstance(candles, list):
                return [
                    {
                        "date": c.get("time", c[0] if isinstance(c, list) else ""),
                        "open": c.get("open", c[1] if isinstance(c, list) else 0),
                        "high": c.get("high", c[2] if isinstance(c, list) else 0),
                        "low": c.get("low", c[3] if isinstance(c, list) else 0),
                        "close": c.get("close", c[4] if isinstance(c, list) else 0),
                        "volume": c.get("volume", 0),
                    }
                    for c in candles
                ]
        except Exception:
            pass
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
        body: dict[str, Any] = {
            "client_id": self.client_id,
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "product": PRODUCT_MIS if product == PRODUCT_MIS else "NRML",
            "order_type": "LIMIT" if order_type == ORDER_LIMIT else "MARKET",
        }
        if order_type == ORDER_LIMIT and price is not None:
            body["price"] = price
        data = self._post("/trade/v1/intraday", body)
        return str(data.get("order_id", data))

    def cancel_order(self, order_id: str) -> str:
        self._post("/trade/v1/cancel", {"client_id": self.client_id, "order_id": order_id})
        return order_id


def ventura_sso_url(app_key: str, state: str = "") -> str:
    return f"{_BASE}/ease-api/v1/login?app_key={app_key}&state={state}"


def ventura_generate_token(app_key: str, secret_key: str, request_token: str) -> dict[str, str]:
    checksum = hashlib.sha256(f"{app_key}{secret_key}".encode()).hexdigest().lower()
    body = {"request_token": request_token, "checksum": checksum}
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{_BASE}/ease-api/v1/auth/token", json=body)
        r.raise_for_status()
        data = r.json().get("data", r.json())
        return {
            "auth_token": data.get("auth_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "client_id": data.get("client_id", ""),
        }


def ventura_totp_login(app_key: str, secret_key: str, client_id: str, totp: str) -> dict[str, str]:
    checksum = hashlib.sha256(f"{app_key}{secret_key}".encode()).hexdigest().lower()
    body = {"client_id": client_id, "totp": totp, "checksum": checksum, "app_key": app_key}
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{_BASE}/ease-api/v1/auth/totp", json=body)
        r.raise_for_status()
        data = r.json().get("data", r.json())
        return {
            "auth_token": data.get("auth_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "client_id": client_id,
        }
