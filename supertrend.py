"""TradingView-style Supertrend (period 10, multiplier 3.0) on Wilder ATR."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from config import SUPERTREND_MULTIPLIER, SUPERTREND_PERIOD
from indicators import add_volume_metrics, volume_filter_ok, wilder_atr

SignalKind = Literal["BUY", "SELL", "HOLD", "NONE"]


def compute_supertrend(
    df: pd.DataFrame,
    period: int = SUPERTREND_PERIOD,
    multiplier: float = SUPERTREND_MULTIPLIER,
) -> pd.DataFrame:
    """
    Add Supertrend columns to a daily OHLCV frame.

    Algorithm matches KivancOzbilgic / TradingView Supertrend:
      basic_lower = HL2 - multiplier * ATR
      basic_upper = HL2 + multiplier * ATR
      final bands ratchet with previous close
      trend flips when close crosses the *previous* final band
      Supertrend line = final_lower (green / bullish) or final_upper (red)
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "businessDate" in out.columns:
        out = out.sort_values("businessDate").reset_index(drop=True)
    else:
        out = out.reset_index(drop=True)

    high = out["high"].to_numpy(dtype=float)
    low = out["low"].to_numpy(dtype=float)
    close = out["close"].to_numpy(dtype=float)
    n = len(out)

    atr = wilder_atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    basic_lower = hl2 - multiplier * atr
    basic_upper = hl2 + multiplier * atr

    final_lower = np.full(n, np.nan)
    final_upper = np.full(n, np.nan)
    trend = np.full(n, np.nan)
    supertrend = np.full(n, np.nan)

    first = period - 1
    for i in range(n):
        if i < first or not np.isfinite(atr[i]):
            continue
        if i == first or not np.isfinite(final_lower[i - 1]):
            final_lower[i] = basic_lower[i]
            final_upper[i] = basic_upper[i]
            trend[i] = 1.0
            supertrend[i] = final_lower[i]
            continue

        if close[i - 1] > final_lower[i - 1]:
            final_lower[i] = max(basic_lower[i], final_lower[i - 1])
        else:
            final_lower[i] = basic_lower[i]

        if close[i - 1] < final_upper[i - 1]:
            final_upper[i] = min(basic_upper[i], final_upper[i - 1])
        else:
            final_upper[i] = basic_upper[i]

        prev_trend = trend[i - 1]
        if prev_trend == -1 and close[i] > final_upper[i - 1]:
            trend[i] = 1.0
        elif prev_trend == 1 and close[i] < final_lower[i - 1]:
            trend[i] = -1.0
        else:
            trend[i] = prev_trend

        supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    prev_trend = np.roll(trend, 1)
    prev_trend[0] = np.nan

    out["atr"] = atr
    out["basic_lower"] = basic_lower
    out["basic_upper"] = basic_upper
    out["final_lower"] = final_lower
    out["final_upper"] = final_upper
    out["trend"] = trend
    out["supertrend"] = supertrend
    out["bullish"] = trend == 1
    out["flip_buy"] = (trend == 1) & (prev_trend == -1)
    out["flip_sell"] = (trend == -1) & (prev_trend == 1)
    return out


def classify_latest(
    df: pd.DataFrame,
    rvol_threshold: float = 1.2,
) -> dict[str, float | bool | str | None]:
    """
    Read the last two Supertrend bars and emit the strategy state.

    Returns a dict consumed by `scanner.evaluate_symbol`.
    """
    if df is None or len(df) < 2:
        return {"signal": "NONE", "ready": False}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    if not np.isfinite(last.get("supertrend", np.nan)):
        return {"signal": "NONE", "ready": False}

    close = float(last["close"])
    st = float(last["supertrend"])
    trend = int(last["trend"])
    prev_trend = int(prev["trend"]) if np.isfinite(prev.get("trend", np.nan)) else 0
    flip_buy = bool(last["flip_buy"])
    flip_sell = bool(last["flip_sell"])

    vol_sma20 = float(last["vol_sma20"]) if np.isfinite(last.get("vol_sma20", np.nan)) else float("nan")
    vol_sma50 = float(last["vol_sma50"]) if np.isfinite(last.get("vol_sma50", np.nan)) else float("nan")
    rvol = float(last["rvol"]) if np.isfinite(last.get("rvol", np.nan)) else float("nan")
    vol_ok = volume_filter_ok(vol_sma20, vol_sma50, rvol, rvol_threshold)

    if flip_buy and vol_ok:
        signal: SignalKind = "BUY"
    elif flip_buy and not vol_ok:
        signal = "NONE"  # green flip rejected by volume — reported as blocked
    elif flip_sell:
        signal = "SELL"
    elif trend == 1:
        signal = "HOLD"
    else:
        signal = "NONE"

    trail = st if trend == 1 else float("nan")
    dist_pct = ((close - st) / close * 100.0) if close and trend == 1 else float("nan")

    return {
        "ready": True,
        "signal": signal,
        "close": close,
        "supertrend": st,
        "trend": trend,
        "prev_trend": prev_trend,
        "flip_buy": flip_buy,
        "flip_sell": flip_sell,
        "volume_ok": vol_ok,
        "vol_sma20": vol_sma20,
        "vol_sma50": vol_sma50,
        "rvol": rvol,
        "trailing_stop": trail,
        "dist_to_trail_pct": dist_pct,
        "atr": float(last["atr"]) if np.isfinite(last.get("atr", np.nan)) else float("nan"),
    }


def enrich_ohlcv(
    df: pd.DataFrame,
    period: int = SUPERTREND_PERIOD,
    multiplier: float = SUPERTREND_MULTIPLIER,
) -> pd.DataFrame:
    """Volume metrics + Supertrend on a single OHLCV frame."""
    return compute_supertrend(add_volume_metrics(df), period=period, multiplier=multiplier)
