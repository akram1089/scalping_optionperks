"""Fyers API v3 adapter."""

import logging
from typing import Any

import httpx

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY

logger = logging.getLogger(__name__)

_BASE = "https://api-t1.fyers.in/api/v3"
_EXCHANGE_MAP = {"NSE": 10, "NFO": 11, "BSE": 12}
_SIDE_MAP = {"BUY": 1, "SELL": -1}
_PRODUCT_MAP = {PRODUCT_MIS: "INTRADAY", "NRML": "MARGIN"}


class FyersBroker:
    broker_slug = "fyers"

    def __init__(self, app_id: str, access_token: str):
        self.app_id = app_id
        self.access_token = access_token
        self._client = httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"{self.app_id}:{self.access_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._client.get(f"{_BASE}{path}", headers=self._headers(), params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("s") != "ok":
            raise RuntimeError(data.get("message", str(data)))
        return data

    def _post(self, path: str, body: dict) -> Any:
        r = self._client.post(f"{_BASE}{path}", json=body, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        if data.get("s") != "ok":
            raise RuntimeError(data.get("message", str(data)))
        return data

    def close(self) -> None:
        self._client.close()

    def _fyers_symbol(self, exchange: str, symbol: str) -> str:
        ex = exchange if exchange in ("NSE", "NFO", "BSE", "MCX") else "NSE"
        return f"{ex}:{symbol}-EQ" if ex == "NSE" and not symbol.endswith("EQ") else f"{ex}:{symbol}"

    def profile(self) -> dict[str, Any]:
        p = self._get("/profile")["data"]
        return {
            "user_id": p.get("fy_id"),
            "user_name": p.get("name"),
            "email": p.get("email_id"),
            "broker": "FYERS",
            "exchanges": [],
            "products": [],
            "order_types": [],
        }

    def margins(self) -> dict[str, Any]:
        m = self._get("/funds")["data"]
        fund = m.get("fund_limit", [{}])[0] if m.get("fund_limit") else {}
        equity = {
            "net": float(fund.get("equityAmount", 0) or 0),
            "available": {
                "live_balance": float(fund.get("equityAmount", 0) or 0),
                "opening_balance": float(fund.get("equityAmount", 0) or 0),
                "collateral": 0.0,
            },
            "utilised": {"debits": 0.0, "m2m_unrealised": 0.0, "m2m_realised": 0.0},
        }
        return {"equity": equity}

    def holdings(self) -> list[dict[str, Any]]:
        return self._get("/holdings")["data"].get("holdings", [])

    def positions(self) -> dict[str, Any]:
        raw = self._get("/positions")["data"].get("netPositions", [])
        net = [
            {
                "tradingsymbol": p.get("symbol", "").split(":")[-1] if ":" in p.get("symbol", "") else p.get("symbol"),
                "quantity": int(p.get("netQty", 0) or 0),
                "pnl": float(p.get("pl", 0) or 0),
            }
            for p in raw
        ]
        return {"net": net, "day": net}

    def orders(self) -> list[dict[str, Any]]:
        return self._get("/orders")["data"].get("orderBook", [])

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        symbols = ",".join(instruments)
        data = self._get("/quotes", params={"symbols": symbols})["data"]
        result = {}
        for q in data:
            sym = q.get("n", "")
            result[sym] = {"last_price": float(q.get("v", {}).get("lp", 0) or 0)}
        return result

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
        resolution_map = {
            "minute": "1",
            "5minute": "5",
            "15minute": "15",
            "30minute": "30",
            "60minute": "60",
            "day": "D",
        }
        fyers_sym = self._fyers_symbol(exchange, symbol)
        params = {
            "symbol": fyers_sym,
            "resolution": resolution_map.get(interval, "5"),
            "date_format": "1",
            "range_from": from_date[:10],
            "range_to": to_date[:10],
            "cont_flag": "1",
        }
        candles = self._get("/history", params=params)["data"].get("candles", [])
        return [
            {
                "date": c[0],
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5] if len(c) > 5 else 0,
            }
            for c in candles
        ]

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
            "symbol": self._fyers_symbol(exchange, symbol),
            "qty": qty,
            "type": 1 if order_type == ORDER_LIMIT else 2,
            "side": _SIDE_MAP.get(side, 1 if side == SIDE_BUY else -1),
            "productType": _PRODUCT_MAP.get(product, "INTRADAY"),
            "limitPrice": price or 0,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
        }
        data = self._post("/orders/sync", body)
        return str(data["data"].get("id", data["data"]))

    def cancel_order(self, order_id: str) -> str:
        self._post(f"/orders/sync", {"id": order_id})
        return order_id


def fyers_login_url(app_id: str, redirect_uri: str, state: str = "") -> str:
    return (
        f"https://api-t1.fyers.in/api/v3/generate-authcode"
        f"?client_id={app_id}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    )


def fyers_generate_token(app_id: str, secret: str, auth_code: str) -> str:
    import hashlib

    app_id_hash = hashlib.sha256(f"{app_id}:{secret}".encode()).hexdigest()
    body = {"grant_type": "authorization_code", "appIdHash": app_id_hash, "code": auth_code}
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{_BASE}/validate-authcode", json=body)
        r.raise_for_status()
        data = r.json()
        if data.get("s") != "ok":
            raise RuntimeError(data.get("message", "Fyers token generation failed"))
        return data["access_token"]
