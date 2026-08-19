"""True Range, Wilder ATR, and volume/turnover overlays."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import VOLUME_SMA_LONG, VOLUME_SMA_SHORT


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Classic True Range: max(H-L, |H-C_prev|, |L-C_prev|)."""
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    ranges = np.vstack(
        (
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        )
    )
    return ranges.max(axis=0)


def wilder_rma(values: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder RMA (TradingView `ta.rma`).

    First value is the SMA of the first `period` observations; later values
    follow `rma = (rma_prev * (period - 1) + x) / period`.
    """
    out = np.full(values.shape, np.nan, dtype=float)
    if period <= 0 or len(values) < period:
        return out
    if np.any(np.isnan(values[:period])):
        # Skip until we have a full clean window.
        start = None
        for i in range(len(values) - period + 1):
            window = values[i : i + period]
            if not np.any(np.isnan(window)):
                start = i
                break
        if start is None:
            return out
    else:
        start = 0
    first = start + period - 1
    out[first] = float(np.mean(values[start : start + period]))
    alpha = 1.0 / period
    for i in range(first + 1, len(values)):
        if np.isnan(values[i]) or np.isnan(out[i - 1]):
            continue
        out[i] = alpha * float(values[i]) + (1.0 - alpha) * float(out[i - 1])
    return out


def wilder_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 10,
) -> np.ndarray:
    """Average True Range using Wilder smoothing over `period` bars."""
    return wilder_rma(true_range(high, low, close), period)


def add_volume_metrics(
    df: pd.DataFrame,
    short: int = VOLUME_SMA_SHORT,
    long: int = VOLUME_SMA_LONG,
) -> pd.DataFrame:
    """
    Attach 20/50-day volume SMAs, relative volume, and turnover.

    RVOL = latest volume / 20-day volume SMA.
    """
    out = df.copy()
    volume = out["volume"].astype(float)
    close = out["close"].astype(float)
    out["vol_sma20"] = volume.rolling(short, min_periods=short).mean()
    out["vol_sma50"] = volume.rolling(long, min_periods=long).mean()
    out["rvol"] = volume / out["vol_sma20"].replace(0, np.nan)
    out["turnover"] = close * volume
    out["turnover_sma20"] = out["turnover"].rolling(short, min_periods=short).mean()
    return out


def volume_filter_ok(
    vol_sma20: float,
    vol_sma50: float,
    rvol: float,
    rvol_threshold: float = 1.2,
) -> bool:
    """BUY filter: 20-day volume SMA > 50-day SMA or RVOL above threshold."""
    expanding = (
        np.isfinite(vol_sma20)
        and np.isfinite(vol_sma50)
        and vol_sma20 > vol_sma50
        and vol_sma50 > 0
    )
    hot = np.isfinite(rvol) and rvol > rvol_threshold
    return bool(expanding or hot)
