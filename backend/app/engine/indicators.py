"""Aladin indicator calculations."""

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
    aladin_signal: float  # WMA of RSI
    aladin_fast: float  # EMA of RSI
    long_bias: bool
    short_bias: bool
    long_cross: bool
    short_cross: bool

    @property
    def hilega(self) -> float:
        return self.aladin_signal

    @property
    def milega(self) -> float:
        return self.aladin_fast


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


def compute_aladin(
    closes: np.ndarray, params: IndicatorParams | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    params = params or IndicatorParams()
    rsi = compute_rsi(closes, params.rsi_length)
    aladin_signal = wma(rsi, params.wma_length)
    aladin_fast = ema(rsi, params.ema_length)
    return rsi, aladin_signal, aladin_fast


def compute_hilega_milega(
    closes: np.ndarray, params: IndicatorParams | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Backward-compatible alias."""
    return compute_aladin(closes, params)


def snapshot_at(
    closes: np.ndarray, params: IndicatorParams | None = None
) -> IndicatorSnapshot | None:
    if len(closes) < 30:
        return None
    rsi_arr, signal_arr, fast_arr = compute_aladin(closes, params)
    params = params or IndicatorParams()
    i = len(closes) - 1
    prev = i - 1
    if np.isnan(rsi_arr[i]) or np.isnan(signal_arr[i]) or np.isnan(fast_arr[i]):
        return None
    if prev < 0 or np.isnan(fast_arr[prev]) or np.isnan(signal_arr[prev]):
        return None

    aladin_fast, aladin_signal = float(fast_arr[i]), float(signal_arr[i])
    prev_fast, prev_signal = float(fast_arr[prev]), float(signal_arr[prev])
    mid = params.mid_level

    long_cross = prev_fast <= prev_signal and aladin_fast > aladin_signal
    short_cross = prev_fast >= prev_signal and aladin_fast < aladin_signal
    long_bias = long_cross and aladin_fast > mid and aladin_signal > mid
    short_bias = short_cross and aladin_fast < mid and aladin_signal < mid

    return IndicatorSnapshot(
        rsi=float(rsi_arr[i]),
        aladin_signal=aladin_signal,
        aladin_fast=aladin_fast,
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
