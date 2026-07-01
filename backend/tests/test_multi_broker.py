"""Tests for broker factory, registry, and account limits."""

import pytest

from app.broker.constants import SUPPORTED_BROKERS
from app.broker.registry import list_brokers
from app.broker.zerodha.adapter import ZerodhaBroker
from app.engine.indicators import compute_aladin, snapshot_at
import numpy as np


def test_supported_brokers_count():
    assert len(SUPPORTED_BROKERS) == 5
    assert "zerodha" in SUPPORTED_BROKERS
    assert "angel_one" in SUPPORTED_BROKERS
    assert "fyers" in SUPPORTED_BROKERS
    assert "kotak" in SUPPORTED_BROKERS
    assert "ventura" in SUPPORTED_BROKERS


def test_list_brokers_metadata():
    brokers = list_brokers()
    assert len(brokers) == 5
    slugs = {b["slug"] for b in brokers}
    assert slugs == set(SUPPORTED_BROKERS)
    for b in brokers:
        assert b["label"]
        assert b["connect_type"]


def test_zerodha_broker_slug():
    assert ZerodhaBroker.broker_slug == "zerodha"


def test_compute_aladin_returns_arrays():
    closes = np.array([100 + i * 0.1 + np.sin(i / 3) for i in range(60)])
    rsi, signal, fast = compute_aladin(closes)
    assert len(rsi) == len(closes)
    assert len(signal) == len(closes)
    assert len(fast) == len(closes)


def test_snapshot_at_aladin_fields():
    closes = np.array([100 + i * 0.1 + np.sin(i / 3) for i in range(60)])
    snap = snapshot_at(closes)
    assert snap is not None
    assert hasattr(snap, "aladin_signal")
    assert hasattr(snap, "aladin_fast")


def test_reject_equity_helper():
    from app.routers.strategies import _reject_equity
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _reject_equity("equity_intraday")
    assert exc.value.status_code == 400

    _reject_equity("futures")
    _reject_equity("options")
