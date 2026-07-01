"""Unified broker service protocol."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrokerService(Protocol):
    """Common interface for all broker adapters."""

    broker_slug: str

    def profile(self) -> dict[str, Any]: ...

    def margins(self) -> dict[str, Any]: ...

    def holdings(self) -> list[dict[str, Any]]: ...

    def positions(self) -> dict[str, Any]: ...

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
    ) -> str: ...

    def cancel_order(self, order_id: str) -> str: ...

    def orders(self) -> list[dict[str, Any]]: ...

    def ltp(self, instruments: list[str]) -> dict[str, Any]: ...

    def historical_data(
        self,
        exchange: str,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str,
    ) -> list[dict[str, Any]]: ...

    def instruments(self, exchange: str = "NSE") -> list[dict[str, Any]]: ...

    def close(self) -> None: ...
