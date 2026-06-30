"""Hilega Milega indicator calculations."""

from dataclasses import dataclass

import numpy as np


@dataclass
class IndicatorParams:
    rsi_length: int = 14
    wma_length: int = 21
    ema_length: int = 3
    mid_level: float = 50.0


@dataclass
class IndicatorSnapshot:
    rsi: float
    hilega: float  # WMA of RSI
    milega: float  # EMA of RSI
    long_bias: bool
    short_bias: bool
    long_cross: bool
    short_cross: bool


def compute_rsi(closes: np.ndarray, length: int = 14) -> np.ndarray:
    if len(closes) < length + 1:
        return np.full(len(closes), np.nan)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    rsi = np.full(len(closes), np.nan)
    avg_gain = np.mean(gains[:length])
    avg_loss = np.mean(losses[:length])
    if avg_loss == 0:
        rsi[length] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[length] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(length + 1, len(closes)):
        avg_gain = (avg_gain * (length - 1) + gains[i - 1]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i - 1]) / length
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def wma(values: np.ndarray, length: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    weights = np.arange(1, length + 1, dtype=float)
    weight_sum = weights.sum()
    for i in range(length - 1, len(values)):
        window = values[i - length + 1 : i + 1]
        if np.any(np.isnan(window)):
            continue
        result[i] = np.dot(window, weights) / weight_sum
    return result


def ema(values: np.ndarray, length: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    alpha = 2.0 / (length + 1)
    start = 0
    while start < len(values) and np.isnan(values[start]):
        start += 1
    if start >= len(values):
        return result
    result[start] = values[start]
    for i in range(start + 1, len(values)):
        if np.isnan(values[i]):
            result[i] = result[i - 1]
        else:
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def compute_hilega_milega(
    closes: np.ndarray, params: IndicatorParams | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    params = params or IndicatorParams()
    rsi = compute_rsi(closes, params.rsi_length)
    hilega = wma(rsi, params.wma_length)
    milega = ema(rsi, params.ema_length)
    return rsi, hilega, milega


def snapshot_at(
    closes: np.ndarray, params: IndicatorParams | None = None
) -> IndicatorSnapshot | None:
    if len(closes) < 30:
        return None
    rsi_arr, hilega_arr, milega_arr = compute_hilega_milega(closes, params)
    params = params or IndicatorParams()
    i = len(closes) - 1
    prev = i - 1
    if np.isnan(rsi_arr[i]) or np.isnan(hilega_arr[i]) or np.isnan(milega_arr[i]):
        return None
    if prev < 0 or np.isnan(milega_arr[prev]) or np.isnan(hilega_arr[prev]):
        return None

    milega, hilega = float(milega_arr[i]), float(hilega_arr[i])
    prev_milega, prev_hilega = float(milega_arr[prev]), float(hilega_arr[prev])
    mid = params.mid_level

    long_cross = prev_milega <= prev_hilega and milega > hilega
    short_cross = prev_milega >= prev_hilega and milega < hilega
    long_bias = long_cross and milega > mid and hilega > mid
    short_bias = short_cross and milega < mid and hilega < mid

    return IndicatorSnapshot(
        rsi=float(rsi_arr[i]),
        hilega=hilega,
        milega=milega,
        long_bias=long_bias,
        short_bias=short_bias,
        long_cross=long_cross,
        short_cross=short_cross,
    )


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, length: int = 14) -> float:
    if len(closes) < length + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return float(np.mean(trs[-length:]))
