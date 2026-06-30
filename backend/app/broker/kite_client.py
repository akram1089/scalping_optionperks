import json
import logging
from typing import Any

from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)


class KiteService:
    def __init__(self, api_key: str, api_secret: str, access_token: str | None = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = KiteConnect(api_key=api_key)
        if access_token:
            self.kite.set_access_token(access_token)

    def login_url(self, redirect_url: str) -> str:
        return self.kite.login_url()

    def generate_session(self, request_token: str) -> dict[str, Any]:
        return self.kite.generate_session(request_token, api_secret=self.api_secret)

    def profile(self) -> dict[str, Any]:
        return self.kite.profile()

    def margins(self) -> dict[str, Any]:
        return self.kite.margins()

    def holdings(self) -> list[dict[str, Any]]:
        return self.kite.holdings()

    def place_order(self, **kwargs: Any) -> str:
        return self.kite.place_order(**kwargs)

    def cancel_order(self, variety: str, order_id: str) -> str:
        return self.kite.cancel_order(variety=variety, order_id=order_id)

    def orders(self) -> list[dict[str, Any]]:
        return self.kite.orders()

    def positions(self) -> dict[str, Any]:
        return self.kite.positions()

    def ltp(self, instruments: list[str]) -> dict[str, Any]:
        return self.kite.ltp(instruments)

    def historical_data(
        self, instrument_token: int, from_date: str, to_date: str, interval: str
    ) -> list[dict[str, Any]]:
        return self.kite.historical_data(instrument_token, from_date, to_date, interval)

    def instruments(self, exchange: str = "NSE") -> list[dict[str, Any]]:
        return self.kite.instruments(exchange)
