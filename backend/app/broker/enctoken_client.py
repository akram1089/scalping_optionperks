"""Zerodha web-session client using enctoken (unofficial OMS API)."""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OMS_ROOT = "https://kite.zerodha.com/oms"
KITE_DASHBOARD = "https://kite.zerodha.com/dashboard"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": KITE_DASHBOARD,
    "Origin": "https://kite.zerodha.com",
    "X-Kite-Version": "3",
}


class EnctokenSessionError(RuntimeError):
    """Raised when enctoken is invalid or expired."""


class _KiteConstants:
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"
    VARIETY_REGULAR = "regular"
    PRODUCT_MIS = "MIS"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_MARKET = "MARKET"


def normalize_enctoken(enctoken: str, user_id: str | None = None) -> str:
    """Strip wrappers users may paste from browser devtools."""
    token = enctoken.strip()
    if token.lower().startswith("enctoken "):
        token = token[9:].strip()
    if user_id and token.startswith(f"{user_id}:"):
        token = token[len(user_id) + 1 :]
    # user_id:token format (wrong for Authorization header)
    if re.match(r"^[A-Z0-9]+:.+", token) and not token.startswith("v="):
        token = token.split(":", 1)[1]
    return token


def _auth_headers(enctoken: str) -> dict[str, str]:
    # Zerodha expects: Authorization: enctoken <raw_cookie_value>
    return {**_BROWSER_HEADERS, "Authorization": f"enctoken {enctoken}"}


def _quote_params(instruments: list[str]) -> list[tuple[str, str]]:
    """Kite expects repeated i= query params (one per instrument)."""
    return [("i", inst) for inst in instruments]


class EnctokenService:
    """Mirrors KiteService interface for enctoken-based web sessions."""

    def __init__(self, user_id: str, enctoken: str):
        self.user_id = user_id
        self.enctoken = normalize_enctoken(enctoken, user_id)
        self.kite = _KiteConstants()
        self._client = httpx.Client(
            timeout=30,
            headers=_auth_headers(self.enctoken),
            cookies={"enctoken": self.enctoken},
        )
        self._warm_session()

    def _warm_session(self) -> None:
        try:
            self._client.get(OMS_ROOT)
        except httpx.HTTPError:
            logger.debug("OMS warm-up request failed (non-fatal)")

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{OMS_ROOT}{path}" if path.startswith("/") else path
        r = self._client.request(method, url, **kwargs)
        if r.status_code in (400, 401, 403):
            msg = _extract_error_message(r)
            logger.warning("Enctoken API %s %s -> %s: %s", method, path, r.status_code, msg)
            raise EnctokenSessionError(
                msg or "Zerodha session invalid or expired — use Reconnect to log in again"
            )
        r.raise_for_status()
        body = r.json()
        if body.get("status") == "error":
            raise RuntimeError(body.get("message", str(body)))
        return body.get("data", body)

    def profile(self) -> dict[str, Any]:
        return self._request("GET", "/user/profile")

    def margins(self) -> dict[str, Any]:
        return self._request("GET", "/user/margins")

    def holdings(self) -> list[dict[str, Any]]:
        return self._request("GET", "/portfolio/holdings")

    def place_order(self, **kwargs: Any) -> str:
        variety = kwargs.pop("variety", self.kite.VARIETY_REGULAR)
        data = self._request("POST", f"/orders/{variety}", data=kwargs)
        return str(data["order_id"])

    def cancel_order(self, variety: str, order_id: str) -> str:
        self._request("DELETE", f"/orders/{variety}/{order_id}")
        return order_id

    def orders(self) -> list[dict[str, Any]]:
        return self._request("GET", "/orders")

    def positions(self) -> dict[str, Any]:
        return self._request("GET", "/portfolio/positions")

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        if not instruments:
            return {}
        return self._request("GET", "/quote/ltp", params=_quote_params(instruments))

    def quote(self, instruments: list[str]) -> dict[str, Any]:
        """Full quote — fallback when /quote/ltp rejects an instrument key."""
        if not instruments:
            return {}
        raw = self._request("GET", "/quote", params=_quote_params(instruments))
        out: dict[str, Any] = {}
        for key, val in raw.items():
            if not isinstance(val, dict):
                continue
            out[key] = {
                "last_price": val.get("last_price"),
                "ohlc": val.get("ohlc") or {},
                "volume": val.get("volume", 0),
            }
        return out

    def historical_data(
        self, instrument_token: int, from_date: str, to_date: str, interval: str
    ) -> list[dict[str, Any]]:
        path = f"/instruments/historical/{instrument_token}/{interval}"
        data = self._request(
            "GET",
            path,
            params={
                "from": from_date,
                "to": to_date,
                "continuous": 0,
                "oi": 0,
            },
        )
        candles = data.get("candles", [])
        return [
            {
                "date": c[0],
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5],
            }
            for c in candles
        ]

    def instruments(self, exchange: str = "NSE") -> list[dict[str, Any]]:
        import csv
        import io

        from app.config import get_settings

        settings = get_settings()
        with httpx.Client(timeout=120) as client:
            r = client.get(settings.kite_instruments_url)
            r.raise_for_status()
            text = r.text
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader if row.get("exchange") == exchange]


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return str(body.get("message") or body.get("error_type") or body)
    except Exception:
        pass
    return response.text[:200] if response.text else ""
