"""Zerodha adapter — wraps Kite Connect and enctoken clients."""

from typing import Any

from app.broker.constants import ORDER_LIMIT, ORDER_MARKET, PRODUCT_MIS, SIDE_BUY, SIDE_SELL
from app.broker.enctoken_client import EnctokenService
from app.broker.kite_client import KiteService


class ZerodhaBroker:
    broker_slug = "zerodha"

    def __init__(self, inner: KiteService | EnctokenService):
        self._inner = inner
        self._is_enctoken = isinstance(inner, EnctokenService)

    def close(self) -> None:
        if self._is_enctoken:
            self._inner.close()

    def profile(self) -> dict[str, Any]:
        return self._inner.profile()

    def margins(self) -> dict[str, Any]:
        return self._inner.margins()

    def holdings(self) -> list[dict[str, Any]]:
        return self._inner.holdings()

    def positions(self) -> dict[str, Any]:
        return self._inner.positions()

    def orders(self) -> list[dict[str, Any]]:
        return self._inner.orders()

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        return self._inner.ltp(instruments)

    def instruments(self, exchange: str = "NSE") -> list[dict[str, Any]]:
        return self._inner.instruments(exchange)

    def _resolve_token(self, exchange: str, symbol: str) -> int:
        for inst in self._inner.instruments(exchange):
            if inst.get("tradingsymbol") == symbol:
                return int(inst["instrument_token"])
        raise ValueError(f"Instrument not found: {exchange}:{symbol}")

    def historical_data(
        self,
        exchange: str,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str,
    ) -> list[dict[str, Any]]:
        token = self._resolve_token(exchange, symbol)
        return self._inner.historical_data(token, from_date, to_date, interval)

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
        kite = self._inner.kite
        txn = kite.TRANSACTION_TYPE_BUY if side == SIDE_BUY else kite.TRANSACTION_TYPE_SELL
        prod = kite.PRODUCT_MIS if product == PRODUCT_MIS else kite.PRODUCT_MIS
        otype = kite.ORDER_TYPE_LIMIT if order_type == ORDER_LIMIT else kite.ORDER_TYPE_MARKET
        kwargs: dict[str, Any] = {
            "variety": kite.VARIETY_REGULAR,
            "exchange": exchange,
            "tradingsymbol": symbol,
            "transaction_type": txn,
            "quantity": qty,
            "product": prod,
            "order_type": otype,
        }
        if otype == kite.ORDER_TYPE_LIMIT and price is not None:
            kwargs["price"] = price
        return self._inner.place_order(**kwargs)

    def cancel_order(self, order_id: str) -> str:
        variety = self._inner.kite.VARIETY_REGULAR
        return self._inner.cancel_order(variety, order_id)
