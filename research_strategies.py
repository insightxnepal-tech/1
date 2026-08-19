#!/usr/bin/env python3
"""
Train/test research for NEPSE strategies. Not a live trading module.

Train: signals with entry date <= 2024-12-31
Test:  signals with entry date >= 2025-01-01
Benchmark: NEPSE index buy-and-hold over the same test window.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

import candle_scanner as cs

CACHE = "data/ohlcv"
TRAIN_END = pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-01")
MIN_BARS = 220
MIN_AVG_VOL = 2_000
HORIZON_CAP = 60


@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry: float
    exit: float
    pnl_pct: float
    hold: int
    reason: str


def load_index() -> pd.DataFrame:
    path = os.path.join(CACHE, "_NEPSE.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["businessDate"])
    else:
        df = cs.fetch_symbol_ohlcv("NEPSE", calendar_days=1600)
        os.makedirs(CACHE, exist_ok=True)
        df.to_csv(path, index=False)
    df = cs.compute_indicators(df)
    df["ret_63"] = df["close"].pct_change(63)
    df["ret_126"] = df["close"].pct_change(126)
    df["ret_21"] = df["close"].pct_change(21)
    return df.set_index("businessDate").sort_index()


def load_stocks() -> dict[str, pd.DataFrame]:
    out = {}
    for path in sorted(glob.glob(os.path.join(CACHE, "*.csv"))):
        symbol = os.path.basename(path).replace(".csv", "")
        if symbol.startswith("_"):
            continue
        df = pd.read_csv(path, parse_dates=["businessDate"])
        if len(df) < MIN_BARS:
            continue
        if float(df["volume"].tail(60).mean()) < MIN_AVG_VOL:
            continue
        ind = cs.compute_indicators(df)
        ind["ret_21"] = ind["close"].pct_change(21)
        ind["ret_63"] = ind["close"].pct_change(63)
        ind["hh63"] = ind["high"].rolling(63).max()
        ind["ll20"] = ind["low"].rolling(20).min()
        ind["vol_x"] = ind["volume"] / ind["vol_ma20"].replace(0, np.nan)
        out[symbol] = ind.set_index("businessDate").sort_index()
    return out


def align_index(stock: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    idx = index.reindex(stock.index)
    stock = stock.copy()
    stock["mkt_close"] = idx["close"]
    stock["mkt_ema200"] = idx["ema200"]
    stock["mkt_ema20"] = idx["ema20"]
    stock["mkt_ret_21"] = idx["ret_21"]
    stock["mkt_ret_63"] = idx["ret_63"]
    stock["rs_63"] = stock["ret_63"] - stock["mkt_ret_63"]
    stock["mkt_up"] = stock["mkt_close"] > stock["mkt_ema200"]
    return stock


def replay(
    df: pd.DataFrame,
    entry: np.ndarray,
    *,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
    max_hold: int = 20,
    exit_below_ema: Optional[str] = None,
    exit_rsi_above: Optional[float] = None,
    one_at_a_time: bool = True,
) -> list[Trade]:
    close = df["close"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    rsi = df["rsi"].to_numpy(dtype=float)
    dates = df.index.to_numpy()
    ema_exit = df[exit_below_ema].to_numpy(dtype=float) if exit_below_ema else None
    n = len(df)
    trades: list[Trade] = []
    i = 0
    while i < n - 1:
        if not entry[i]:
            i += 1
            continue
        px = close[i]
        if not np.isfinite(px) or px <= 0:
            i += 1
            continue
        exit_j = None
        reason = "time"
        last = min(n - 1, i + max_hold)
        for j in range(i + 1, last + 1):
            ret = close[j] / px - 1.0
            if sl is not None and (low[j] / px - 1.0) <= -sl:
                # stop assumed filled at stop level (conservative vs close)
                exit_j = j
                reason = "stop"
                # use worse of close or stop
                break
            if tp is not None and (high[j] / px - 1.0) >= tp:
                exit_j = j
                reason = "target"
                break
            if ema_exit is not None and np.isfinite(ema_exit[j]) and close[j] < ema_exit[j]:
                exit_j = j
                reason = f"below_{exit_below_ema}"
                break
            if exit_rsi_above is not None and rsi[j] >= exit_rsi_above:
                exit_j = j
                reason = "rsi"
                break
        if exit_j is None:
            exit_j = last
            reason = "time"
        exit_px = close[exit_j]
        if reason == "stop" and sl is not None:
            exit_px = px * (1.0 - sl)
        elif reason == "target" and tp is not None:
            exit_px = px * (1.0 + tp)
        pnl = (exit_px / px - 1.0) * 100.0
        trades.append(
            Trade(
                symbol="",
                entry_date=pd.Timestamp(dates[i]),
                exit_date=pd.Timestamp(dates[exit_j]),
                entry=float(px),
                exit=float(exit_px),
                pnl_pct=float(pnl),
                hold=int(exit_j - i),
                reason=reason,
            )
        )
        i = exit_j + 1 if one_at_a_time else i + 1
    return trades


def score(trades: list[Trade], label: str) -> dict:
    if not trades:
        return {"split": label, "n": 0, "win": None, "avg": None, "med": None, "exp": None}
    pnls = np.array([t.pnl_pct for t in trades], dtype=float)
    wins = pnls > 0
    return {
        "split": label,
        "n": int(len(trades)),
        "win": round(float(wins.mean() * 100), 1),
        "avg": round(float(pnls.mean()), 2),
        "med": round(float(np.median(pnls)), 2),
        "exp": round(float(pnls.mean()), 2),
        "hold": round(float(np.mean([t.hold for t in trades])), 1),
        "stops": int(sum(t.reason == "stop" for t in trades)),
        "targets": int(sum(t.reason == "target" for t in trades)),
    }


def split_trades(trades: list[Trade]) -> tuple[list[Trade], list[Trade]]:
    train = [t for t in trades if t.entry_date <= TRAIN_END]
    test = [t for t in trades if t.entry_date >= TEST_START]
    return train, test


def portfolio_vs_index(trades: list[Trade], index: pd.DataFrame, max_pos: int = 8) -> dict:
    """Equal 1/max_pos capital per slot; cash otherwise. Daily marked to exit price path via pnl at exit."""
    if not trades:
        return {"port": None, "mkt": None, "excess": None}
    start = min(t.entry_date for t in trades)
    end = max(t.exit_date for t in trades)
    cal = index.loc[(index.index >= start) & (index.index <= end)].copy()
    if cal.empty:
        return {"port": None, "mkt": None, "excess": None}
    # Approximate: deploy 1/max_pos at entry, realize pnl at exit, idle cash = 0 return.
    nav = 1.0
    open_slots = []
    by_entry = {}
    for t in trades:
        by_entry.setdefault(t.entry_date.normalize(), []).append(t)
    dates = list(cal.index)
    i_tr = 0
    # Simpler equity curve: sequential compounding of trade pnls in calendar order of exit,
    # with occupancy cap approximated by skipping entries when 8 already open.
    active: list[Trade] = []
    realized = []
    for dt in dates:
        active = [t for t in active if t.exit_date > dt]
        incoming = by_entry.get(pd.Timestamp(dt).normalize(), [])
        for t in incoming:
            if len(active) >= max_pos:
                continue
            active.append(t)
        for t in list(active):
            if t.exit_date == dt:
                realized.append(t)
                active.remove(t)
    if not realized:
        return {"port": None, "mkt": None, "excess": None}
    # Compound equal-risk: each trade uses 1/max_pos of NAV
    nav = 1.0
    for t in sorted(realized, key=lambda x: x.exit_date):
        nav *= 1.0 + (t.pnl_pct / 100.0) / max_pos
    mkt0 = float(cal["close"].iloc[0])
    mkt1 = float(cal["close"].iloc[-1])
    mkt = (mkt1 / mkt0 - 1.0) * 100.0
    port = (nav - 1.0) * 100.0
    return {
        "port": round(port, 2),
        "mkt": round(mkt, 2),
        "excess": round(port - mkt, 2),
        "n_taken": len(realized),
    }


def near_ema(df: pd.DataFrame, col: str, pct: float = 0.015) -> np.ndarray:
    close = df["close"].to_numpy(dtype=float)
    ema = df[col].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    dist = np.maximum(close * pct, close * 0.005)
    bounced = (low <= ema + dist) & (close >= ema - dist)
    closed_near = np.abs(close - ema) <= dist
    green = close > df["open"].to_numpy(dtype=float)
    return green & (bounced | closed_near)


def run_one(name: str, stocks: dict[str, pd.DataFrame], index: pd.DataFrame, entry_fn, **replay_kw) -> dict:
    all_tr: list[Trade] = []
    for sym, raw in stocks.items():
        df = align_index(raw, index)
        try:
            mask = entry_fn(df)
        except Exception:
            continue
        if mask is None or mask.sum() == 0:
            continue
        tr = replay(df, np.asarray(mask, dtype=bool), **replay_kw)
        for t in tr:
            t.symbol = sym
        all_tr.extend(tr)
    train, test = split_trades(all_tr)
    row = {
        "name": name,
        "train": score(train, "train"),
        "test": score(test, "test"),
        "test_vs_mkt": portfolio_vs_index(test, index),
        "n_all": len(all_tr),
    }
    return row


def main() -> int:
    print("Loading index + stocks...")
    index = load_index()
    stocks = load_stocks()
    print(f"Index {len(index)} bars; stocks {len(stocks)}")

    def e_pullback_bull(df):
        rsi = df["rsi"].to_numpy()
        return (
            (df["close"] > df["ema200"])
            & df["mkt_up"].fillna(False)
            & (df["rs_63"] > 0)
            & (rsi >= 35)
            & (rsi <= 48)
            & near_ema(df, "ema20", 0.02)
            & (df["vol_x"] > 1.0)
        )

    def e_pullback_strict(df):
        rsi = df["rsi"].to_numpy()
        return (
            (df["close"] > df["ema200"])
            & (df["ema20"] > df["ema200"])
            & df["mkt_up"].fillna(False)
            & (df["mkt_ret_21"] > 0)
            & (df["rs_63"] > 0.02)
            & (rsi >= 38)
            & (rsi <= 46)
            & near_ema(df, "ema20", 0.015)
            & (df["vol_x"] > 1.2)
            & (df["close"] > df["open"])
        )

    def e_oversold_uptrend(df):
        rsi = df["rsi"].to_numpy()
        return (
            (df["close"] > df["ema200"])
            & df["mkt_up"].fillna(False)
            & (rsi < 35)
            & (df["vol_x"] > 0.8)
        )

    def e_breakout(df):
        prev_hh = df["hh63"].shift(1)
        return (
            (df["close"] > prev_hh)
            & (df["close"] > df["ema200"])
            & df["mkt_up"].fillna(False)
            & (df["vol_x"] > 1.5)
            & (df["rs_63"] > 0)
        )

    def e_rs_dip(df):
        rsi = df["rsi"].to_numpy()
        return (
            df["mkt_up"].fillna(False)
            & (df["close"] > df["ema200"])
            & (df["rs_63"] > 0.05)
            & (rsi >= 40)
            & (rsi <= 50)
            & (df["close"] > df["open"])
            & (df["vol_x"] > 1.0)
        )

    def e_bank_like_quality(df):
        rsi = df["rsi"].to_numpy()
        # liquid names already filtered; require higher price so tick/circuit noise is smaller
        return (
            (df["close"] > 200)
            & (df["close"] > df["ema200"])
            & (df["ema20"] > df["ema200"])
            & df["mkt_up"].fillna(False)
            & (df["mkt_close"] > df["mkt_ema20"])
            & (df["rs_63"] > 0)
            & (rsi >= 36)
            & (rsi <= 48)
            & near_ema(df, "ema20", 0.02)
            & (df["vol_x"] > 1.1)
        )

    configs = [
        ("pullback_tp5_sl8_h12", e_pullback_bull, dict(tp=0.05, sl=0.08, max_hold=12)),
        ("pullback_tp6_sl6_h10", e_pullback_bull, dict(tp=0.06, sl=0.06, max_hold=10)),
        ("pullback_tp4_sl10_h15", e_pullback_bull, dict(tp=0.04, sl=0.10, max_hold=15)),
        ("pullback_tp8_sl7_ema50", e_pullback_bull, dict(tp=0.08, sl=0.07, max_hold=20, exit_below_ema="ema20")),
        ("strict_tp5_sl8_h15", e_pullback_strict, dict(tp=0.05, sl=0.08, max_hold=15)),
        ("strict_tp6_sl9_h20", e_pullback_strict, dict(tp=0.06, sl=0.09, max_hold=20)),
        ("strict_rsi60_sl8", e_pullback_strict, dict(sl=0.08, max_hold=15, exit_rsi_above=60)),
        ("oversold_tp7_sl6_h10", e_oversold_uptrend, dict(tp=0.07, sl=0.06, max_hold=10)),
        ("oversold_tp5_sl8_h12", e_oversold_uptrend, dict(tp=0.05, sl=0.08, max_hold=12)),
        ("breakout_tp10_sl7_h20", e_breakout, dict(tp=0.10, sl=0.07, max_hold=20)),
        ("breakout_trail20_sl8", e_breakout, dict(sl=0.08, max_hold=25, exit_below_ema="ema20")),
        ("rs_dip_tp5_sl8_h12", e_rs_dip, dict(tp=0.05, sl=0.08, max_hold=12)),
        ("quality_tp5_sl8_h12", e_bank_like_quality, dict(tp=0.05, sl=0.08, max_hold=12)),
        ("quality_tp6_sl10_h18", e_bank_like_quality, dict(tp=0.06, sl=0.10, max_hold=18)),
        ("quality_tp4_sl8_h10", e_bank_like_quality, dict(tp=0.04, sl=0.08, max_hold=10)),
        ("quality_rsi58_sl9", e_bank_like_quality, dict(sl=0.09, max_hold=16, exit_rsi_above=58)),
    ]

    rows = []
    for name, fn, kw in configs:
        print(f"  running {name}...")
        row = run_one(name, stocks, index, fn, **kw)
        rows.append(row)
        t, s = row["train"], row["test"]
        vs = row["test_vs_mkt"]
        print(
            f"    train n={t['n']} win={t['win']} avg={t['avg']} | "
            f"test n={s['n']} win={s['win']} avg={s['avg']} | "
            f"port={vs.get('port')} mkt={vs.get('mkt')} excess={vs.get('excess')}"
        )

    os.makedirs("research", exist_ok=True)
    with open("research/strategy_grid.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
        f.write("\n")

    # Rank test set: require n>=30, then sort by win then excess
    viable = [r for r in rows if (r["test"]["n"] or 0) >= 25]
    viable.sort(key=lambda r: ((r["test"]["win"] or 0), (r["test_vs_mkt"].get("excess") or -999)), reverse=True)
    print("\nTop test configs:")
    for r in viable[:8]:
        print(r["name"], r["test"], r["test_vs_mkt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
