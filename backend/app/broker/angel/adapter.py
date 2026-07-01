"""Angel One SmartAPI adapter."""

import logging
from typing import Any

import httpx

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY, SIDE_SELL

logger = logging.getLogger(__name__)

_BASE = "https://apiconnect.angelone.in"
_EXCHANGE_MAP = {"NSE": "NSE", "NFO": "NFO", "BSE": "BSE"}
_PRODUCT_MAP = {PRODUCT_MIS: "INTRADAY", "NRML": "CARRYFORWARD"}


class AngelOneBroker:
    broker_slug = "angel_one"

    def __init__(self, api_key: str, jwt_token: str, feed_token: str = ""):
        self.api_key = api_key
        self.jwt_token = jwt_token
        self.feed_token = feed_token
        self._client = httpx.Client(timeout=30)
        self._symbol_cache: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {self.jwt_token}",
        }

    def _post(self, path: str, body: dict) -> Any:
        r = self._client.post(f"{_BASE}{path}", json=body, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        if not data.get("status"):
            raise RuntimeError(data.get("message", str(data)))
        return data.get("data", data)

    def _get(self, path: str) -> Any:
        r = self._client.get(f"{_BASE}{path}", headers=self._headers())
        r.raise_for_status()
        data = r.json()
        if not data.get("status"):
            raise RuntimeError(data.get("message", str(data)))
        return data.get("data", data)

    def close(self) -> None:
        self._client.close()

    def profile(self) -> dict[str, Any]:
        p = self._get("/rest/secure/angelbroking/user/v1/getProfile")
        return {
            "user_id": p.get("clientcode"),
            "user_name": p.get("name"),
            "email": p.get("email"),
            "broker": "ANGEL",
            "exchanges": p.get("exchanges", []),
            "products": p.get("products", []),
            "order_types": p.get("ordertypes", []),
        }

    def margins(self) -> dict[str, Any]:
        m = self._get("/rest/secure/angelbroking/user/v1/getRMS")
        equity = {
            "net": float(m.get("net", 0) or 0),
            "available": {
                "live_balance": float(m.get("availablecash", 0) or 0),
                "opening_balance": float(m.get("availablecash", 0) or 0),
                "collateral": float(m.get("collateral", 0) or 0),
            },
            "utilised": {
                "debits": float(m.get("utiliseddebits", 0) or 0),
                "m2m_unrealised": float(m.get("m2munrealized", 0) or 0),
                "m2m_realised": float(m.get("m2mrealized", 0) or 0),
            },
        }
        return {"equity": equity}

    def holdings(self) -> list[dict[str, Any]]:
        return self._get("/rest/secure/angelbroking/portfolio/v1/getHolding") or []

    def positions(self) -> dict[str, Any]:
        raw = self._get("/rest/secure/angelbroking/order/v1/getPosition") or []
        net = [
            {
                "tradingsymbol": p.get("tradingsymbol"),
                "quantity": int(p.get("netqty", 0) or 0),
                "pnl": float(p.get("pnl", 0) or 0),
            }
            for p in raw
        ]
        return {"net": net, "day": net}

    def orders(self) -> list[dict[str, Any]]:
        return self._get("/rest/secure/angelbroking/order/v1/getOrderBook") or []

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        result = {}
        for inst in instruments:
            parts = inst.split(":")
            exchange = parts[0] if len(parts) > 1 else "NSE"
            symbol = parts[-1]
            token = self._symbol_token(exchange, symbol)
            data = self._post(
                "/rest/secure/angelbroking/order/v1/getLtpData",
                {"exchange": exchange, "tradingsymbol": symbol, "symboltoken": token},
            )
            result[inst] = {"last_price": float(data.get("ltp", 0) or 0)}
        return result

    def _symbol_token(self, exchange: str, symbol: str) -> str:
        key = f"{exchange}:{symbol}"
        if key in self._symbol_cache:
            return self._symbol_cache[key]
        # Angel master search via symbol token API pattern — cache from order book
        self._symbol_cache[key] = symbol
        return symbol

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
        interval_map = {
            "minute": "ONE_MINUTE",
            "3minute": "THREE_MINUTE",
            "5minute": "FIVE_MINUTE",
            "15minute": "FIFTEEN_MINUTE",
            "30minute": "THIRTY_MINUTE",
            "60minute": "ONE_HOUR",
            "day": "ONE_DAY",
        }
        body = {
            "exchange": _EXCHANGE_MAP.get(exchange, exchange),
            "symboltoken": self._symbol_token(exchange, symbol),
            "interval": interval_map.get(interval, "FIVE_MINUTE"),
            "fromdate": from_date[:10] + " 09:15",
            "todate": to_date[:10] + " 15:30",
        }
        candles = self._post("/rest/secure/angelbroking/historical/v1/getCandleData", body) or []
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
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": self._symbol_token(exchange, symbol),
            "transactiontype": side,
            "exchange": _EXCHANGE_MAP.get(exchange, exchange),
            "ordertype": "LIMIT" if order_type == ORDER_LIMIT else "MARKET",
            "producttype": _PRODUCT_MAP.get(product, "INTRADAY"),
            "duration": "DAY",
            "quantity": str(qty),
        }
        if order_type == ORDER_LIMIT and price is not None:
            body["price"] = str(price)
        data = self._post("/rest/secure/angelbroking/order/v1/placeOrder", body)
        return str(data.get("orderid", data))

    def cancel_order(self, order_id: str) -> str:
        self._post(
            "/rest/secure/angelbroking/order/v1/cancelOrder",
            {"variety": "NORMAL", "orderid": order_id},
        )
        return order_id


def angel_login(api_key: str, client_code: str, password: str, totp: str) -> dict[str, str]:
    """Authenticate with Angel One SmartAPI and return tokens."""
    body = {"clientcode": client_code, "password": password, "totp": totp}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": "00:00:00:00:00:00",
        "X-PrivateKey": api_key,
    }
    with httpx.Client(timeout=30) as client:
        r = client.post(
            f"{_BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
            json=body,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("status"):
            raise RuntimeError(data.get("message", "Angel login failed"))
        d = data["data"]
        return {
            "jwt_token": d["jwtToken"],
            "refresh_token": d.get("refreshToken", ""),
            "feed_token": d.get("feedToken", ""),
        }
