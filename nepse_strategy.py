#!/usr/bin/env python3
"""
NEPSE barbell strategy.

Core (beat-the-market sleeve)
  Hold NEPSE while daily RSI(14) is in a risk-on cycle.
  Go to cash when RSI >= 80; re-enter when RSI <= 40.

Satellite (high-hit-rate overlay, optional, small size)
  Only while NEPSE close > 200 EMA.
  Buy liquid names that are above the 200 EMA, 20 EMA > 200 EMA,
  63-day relative strength > 0, RSI(14) < 42, volume > 20-day MA.
  Exit +3% target, -12% stop, or 30 sessions.

The 75%+ satellite hit rate comes mainly from a 3/12 target-stop ratio plus a
bull filter. It is not a standalone book that beat NEPSE after costs.
Not financial advice.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

import candle_scanner as cs
from research_strategies import (
    TEST_START,
    TRAIN_END,
    Trade,
    align_index,
    load_index,
    load_stocks,
    near_ema,
    replay,
    score,
    split_trades,
)

RSI_SELL = 80.0
RSI_BUY = 40.0
SAT_TP = 0.03
SAT_SL = 0.12
SAT_HOLD = 30
SAT_RSI_MAX = 42.0
CORE_ALLOC = 0.80
SAT_ALLOC = 0.20
MAX_SAT_POS = 5
ROUND_TRIP_COST_PCT = 0.50  # satellite stocks
INDEX_COST_PCT = 0.10  # one-way-ish; index/fund products are cheaper

REPORT_FILE = os.getenv("NEPSE_STRATEGY_REPORT", "nepse_strategy_report.md")
LATEST_FILE = os.getenv("NEPSE_STRATEGY_LATEST", "nepse_strategy_latest.json")
SCAN_FILE = os.getenv("NEPSE_STRATEGY_SCAN", "nepse_strategy_scan.json")


@dataclass
class Regime:
    date: str
    close: float
    rsi: float
    ema200: float
    risk_on: bool
    reason: str


def rsi_cycle_mask(rsi: np.ndarray, sell: float = RSI_SELL, buy: float = RSI_BUY) -> np.ndarray:
    """Start invested. Flatten at RSI>=sell; re-enter at RSI<=buy."""
    pos = np.ones(len(rsi), dtype=float)
    state = 1.0
    for i, val in enumerate(rsi):
        if not np.isfinite(val):
            pos[i] = state
            continue
        if state == 1.0 and val >= sell:
            state = 0.0
        elif state == 0.0 and val <= buy:
            state = 1.0
        pos[i] = state
    return pos


def current_regime(index: pd.DataFrame) -> Regime:
    last = index.iloc[-1]
    rsi = index["rsi"].to_numpy(dtype=float)
    pos = rsi_cycle_mask(rsi)
    risk_on = bool(pos[-1] == 1.0)
    if risk_on:
        reason = f"RISK-ON (RSI {float(last['rsi']):.1f} ≤ {RSI_SELL:.0f} cycle; re-entry at ≤ {RSI_BUY:.0f})"
    else:
        reason = f"CASH (RSI hit {RSI_SELL:.0f}; wait for RSI ≤ {RSI_BUY:.0f})"
    date = last.name
    if hasattr(date, "strftime"):
        date_str = date.strftime("%Y-%m-%d")
    else:
        date_str = str(date)[:10]
    return Regime(
        date=date_str,
        close=round(float(last["close"]), 2),
        rsi=round(float(last["rsi"]), 1),
        ema200=round(float(last["ema200"]), 2),
        risk_on=risk_on,
        reason=reason,
    )


def index_cycle_backtest(index: pd.DataFrame, start: str, end: str) -> dict:
    cal = index.loc[start:end].copy()
    if len(cal) < 5:
        return {}
    rsi = cal["rsi"].to_numpy(dtype=float)
    pos = rsi_cycle_mask(rsi)
    ret = cal["close"].pct_change().fillna(0.0).to_numpy()
    exec_pos = np.roll(pos, 1)
    exec_pos[0] = pos[0]
    strat = (1.0 + ret * exec_pos).prod() - 1.0
    bh = float(cal["close"].iloc[-1] / cal["close"].iloc[0] - 1.0)
    # Cycle trades (close-to-close, no cost on index except small)
    trades = []
    state = int(pos[0])
    entry_px = float(cal["close"].iloc[0])
    entry_i = 0
    closes = cal["close"].to_numpy(dtype=float)
    dates = cal.index
    for i in range(1, len(pos)):
        if state == 1 and pos[i] == 0:
            pnl = (closes[i] / entry_px - 1.0) * 100.0 - INDEX_COST_PCT
            trades.append(
                {
                    "entry": dates[entry_i].strftime("%Y-%m-%d"),
                    "exit": dates[i].strftime("%Y-%m-%d"),
                    "pnl_pct": round(pnl, 2),
                    "hold": int(i - entry_i),
                    "open": False,
                }
            )
            state = 0
        elif state == 0 and pos[i] == 1:
            entry_px = float(closes[i])
            entry_i = i
            state = 1
    if state == 1:
        pnl = (closes[-1] / entry_px - 1.0) * 100.0
        trades.append(
            {
                "entry": dates[entry_i].strftime("%Y-%m-%d"),
                "exit": dates[-1].strftime("%Y-%m-%d"),
                "pnl_pct": round(pnl, 2),
                "hold": int(len(pos) - 1 - entry_i),
                "open": True,
            }
        )
    closed = [t for t in trades if not t["open"]]
    wins = [t for t in closed if t["pnl_pct"] > 0]
    return {
        "start": pd.Timestamp(cal.index[0]).strftime("%Y-%m-%d"),
        "end": pd.Timestamp(cal.index[-1]).strftime("%Y-%m-%d"),
        "strategy_pct": round(strat * 100, 2),
        "nepse_bh_pct": round(bh * 100, 2),
        "excess_pct": round((strat - bh) * 100, 2),
        "time_in_market_pct": round(float(exec_pos.mean()) * 100, 1),
        "cycles_closed": len(closed),
        "cycle_win_pct": round(100.0 * len(wins) / len(closed), 1) if closed else None,
        "cycle_avg_pct": round(float(np.mean([t["pnl_pct"] for t in closed])), 2) if closed else None,
        "trades": trades,
    }


def satellite_entry_mask(df: pd.DataFrame) -> np.ndarray:
    rsi = df["rsi"].to_numpy(dtype=float)
    mkt_up = df["mkt_up"].fillna(False).to_numpy(dtype=bool)
    rs = df["rs_63"].fillna(-1).to_numpy(dtype=float)
    return (
        (df["close"].to_numpy(dtype=float) > df["ema200"].to_numpy(dtype=float))
        & (df["ema20"].to_numpy(dtype=float) > df["ema200"].to_numpy(dtype=float))
        & mkt_up
        & (rs > 0)
        & (rsi < SAT_RSI_MAX)
        & (df["vol_x"].to_numpy(dtype=float) > 1.0)
    )


def satellite_backtest(stocks: dict[str, pd.DataFrame], index: pd.DataFrame) -> dict:
    all_tr: list[Trade] = []
    for sym, raw in stocks.items():
        df = align_index(raw, index)
        mask = satellite_entry_mask(df)
        tr = replay(df, mask, tp=SAT_TP, sl=SAT_SL, max_hold=SAT_HOLD)
        for t in tr:
            t.symbol = sym
            t.pnl_pct = t.pnl_pct - ROUND_TRIP_COST_PCT
        all_tr.extend(tr)
    train, test = split_trades(all_tr)
    return {
        "train": score(train, "train"),
        "test": score(test, "test"),
        "n_all": len(all_tr),
        "cost_pct": ROUND_TRIP_COST_PCT,
        "rules": {
            "tp": SAT_TP,
            "sl": SAT_SL,
            "max_hold": SAT_HOLD,
            "rsi_max": SAT_RSI_MAX,
        },
    }


def scan_satellite(
    stocks: dict[str, pd.DataFrame],
    index: pd.DataFrame,
    meta: Optional[dict[str, cs.ListedScript]] = None,
) -> list[dict]:
    meta = meta or {}
    hits = []
    for sym, raw in stocks.items():
        df = align_index(raw, index)
        if len(df) < cs.MIN_HISTORY:
            continue
        mask = satellite_entry_mask(df)
        if not bool(mask[-1]):
            continue
        last = df.iloc[-1]
        info = meta.get(sym)
        hits.append(
            {
                "symbol": sym,
                "name": info.name if info else "",
                "sector": info.sector if info else "",
                "close": round(float(last["close"]), 2),
                "rsi": round(float(last["rsi"]), 1),
                "ema20": round(float(last["ema20"]), 2),
                "ema200": round(float(last["ema200"]), 2),
                "rs_63": round(float(last["rs_63"]) * 100, 1) if pd.notna(last["rs_63"]) else None,
                "vol_x": round(float(last["vol_x"]), 2) if pd.notna(last["vol_x"]) else None,
                "target": round(float(last["close"]) * (1 + SAT_TP), 2),
                "stop": round(float(last["close"]) * (1 - SAT_SL), 2),
            }
        )
    hits.sort(key=lambda r: (r["rs_63"] is not None, r["rs_63"] or -999), reverse=True)
    return hits[: MAX_SAT_POS * 2]


def format_report(core_train: dict, core_test: dict, core_full: dict, sat: dict, regime: Regime) -> str:
    def cycle_table(block: dict) -> str:
        lines = [
            f"- Window: **{block['start']} → {block['end']}**",
            f"- Strategy: **{block['strategy_pct']:+.2f}%** vs NEPSE buy-and-hold **{block['nepse_bh_pct']:+.2f}%** (excess **{block['excess_pct']:+.2f} pts**)",
            f"- Time in market: **{block['time_in_market_pct']}%**",
            f"- Closed RSI cycles: **{block['cycles_closed']}**, win **{block['cycle_win_pct']}%**, avg **{block['cycle_avg_pct']}%**" if block.get("cycle_win_pct") is not None else f"- Closed RSI cycles: **{block['cycles_closed']}**",
            "",
        ]
        if block.get("trades"):
            lines += [
                "| Entry | Exit | P/L | Hold | Status |",
                "| --- | --- | ---: | ---: | --- |",
            ]
            for t in block["trades"]:
                st = "open" if t["open"] else "closed"
                lines.append(f"| {t['entry']} | {t['exit']} | {t['pnl_pct']:+.2f}% | {t['hold']}d | {st} |")
            lines.append("")
        return "\n".join(lines)

    tr, te = sat["train"], sat["test"]
    lines = [
        "# NEPSE barbell strategy",
        "",
        f"Generated **{datetime.now(timezone.utc).strftime('%Y-%m-%d')}**. Unofficial merolagani OHLCV. Not financial advice.",
        "",
        "## What the data supports (and what it does not)",
        "",
        "The old 4-rule candle scanner had a **27.5%** paper-trade win rate and did not beat NEPSE.",
        "",
        f"A stock-picking system with **>75% accuracy and market-beating returns after NEPSE costs was not found** on a 2023–2024 train / 2025–2026 test split (213 liquid ordinary equities). 20-session directional accuracy for “stock above 200 EMA” was **48% train / 37% test** — a coin flip, not 75%.",
        "",
        "Two sleeves *are* justified:",
        "",
        f"1. **Core — NEPSE RSI cycle ({RSI_SELL:.0f}/{RSI_BUY:.0f})** beat buy-and-hold over the full window by sitting in cash after extreme overbought prints.",
        f"2. **Satellite — 3% target / 12% stop bounce** printed **>75%** out-of-sample hit rate. That hit rate is mostly the 3-to-12 barrier ratio plus a bull filter. After **{ROUND_TRIP_COST_PCT:.1f}%** round-trip costs it did **not** beat NEPSE as a standalone book. Cap it at **{int(SAT_ALLOC*100)}%** of capital.",
        "",
        f"## Today's regime ({regime.date})",
        "",
        f"- NEPSE **{regime.close:.2f}** · RSI **{regime.rsi:.1f}** · 200 EMA **{regime.ema200:.2f}**",
        f"- **{regime.reason}**",
        "",
        f"If RISK-ON: hold NEPSE (or an index-tracking fund) for ~{int(CORE_ALLOC*100)}% of the book. If CASH: no new stock overlay either.",
        "",
        "## Core: NEPSE RSI 80 / 40",
        "",
        "Start invested. When daily RSI(14) closes **≥ 80**, go to cash (next session). When RSI closes **≤ 40**, buy NEPSE back. One position; no leverage.",
        "",
        "### Train (through 2024)",
        "",
        cycle_table(core_train),
        "### Test (2025 onward)",
        "",
        cycle_table(core_test),
        "### Full sample",
        "",
        cycle_table(core_full),
        "Closed-cycle counts are small. The NAV edge vs buy-and-hold is the real test, not the 100% cycle hit rate.",
        "",
        "## Satellite: high-hit-rate bounce (optional)",
        "",
        "All of:",
        "",
        "- NEPSE close > 200 EMA",
        "- Stock close > 200 EMA and 20 EMA > 200 EMA",
        "- 63-day return ahead of NEPSE",
        f"- RSI(14) < {SAT_RSI_MAX:.0f}",
        "- Volume > 20-day average",
        "",
        f"Exit: **+{SAT_TP*100:.0f}%** target, **−{SAT_SL*100:.0f}%** stop, or **{SAT_HOLD}** sessions. Max **{MAX_SAT_POS}** names. Size **{int(SAT_ALLOC*100 / MAX_SAT_POS)}%** of the total book per name.",
        "",
        f"After {ROUND_TRIP_COST_PCT:.1f}% round-trip cost:",
        "",
        "| Split | Trades | Win rate | Avg P/L | Avg hold |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Train ≤ 2024 | {tr.get('n', 0)} | {tr.get('win', '—')}% | {tr.get('avg', '—')}% | {tr.get('hold', '—')}d |",
        f"| Test ≥ 2025 | {te.get('n', 0)} | {te.get('win', '—')}% | {te.get('avg', '—')}% | {te.get('hold', '—')}d |",
        "",
        "Use this sleeve for hit-rate, not for beating NEPSE. If train and test win rates both stay above 75% but average P/L after costs is ~0, the overlay is optional.",
        "",
        "## How to run",
        "",
        "```bash",
        "python nepse_strategy.py --backtest",
        "python nepse_strategy.py --scan",
        "```",
        "",
        "Not financial advice. Survivorship (currently listed names only), unofficial prices, and NEPSE commissions matter.",
        "",
    ]
    return "\n".join(lines)


def run_backtest(persist: bool = True) -> dict:
    print("Loading NEPSE + stocks...")
    index = load_index()
    stocks = load_stocks()
    core_train = index_cycle_backtest(index, "2023-02-01", "2024-12-31")
    core_test = index_cycle_backtest(index, "2025-01-01", "2026-12-31")
    core_full = index_cycle_backtest(index, "2023-02-01", "2026-12-31")
    print("Core train", {k: core_train[k] for k in ("strategy_pct", "nepse_bh_pct", "excess_pct", "cycle_win_pct")})
    print("Core test ", {k: core_test[k] for k in ("strategy_pct", "nepse_bh_pct", "excess_pct", "cycle_win_pct")})
    print("Scoring satellite...")
    sat = satellite_backtest(stocks, index)
    print("Sat train", sat["train"])
    print("Sat test ", sat["test"])
    regime = current_regime(index)
    report = format_report(core_train, core_test, core_full, sat, regime)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "regime": asdict(regime),
        "core": {"train": core_train, "test": core_test, "full": core_full},
        "satellite": {k: v for k, v in sat.items() if k != "trades"},
        "report": report,
    }
    if persist:
        slim = {k: v for k, v in payload.items() if k != "report"}
        cs.save_json(LATEST_FILE, slim)
        with open(REPORT_FILE, "w") as f:
            f.write(report)
        print(f"Saved {REPORT_FILE}, {LATEST_FILE}")
    print(report)
    return payload


def run_scan(persist: bool = True) -> dict:
    index = load_index()
    stocks = load_stocks()
    listed = []
    raw = cs.load_json(cs.UNIVERSE_FILE, [])
    listed = [cs.ListedScript(**row) for row in raw if isinstance(row, dict) and row.get("symbol")]
    meta = {s.symbol: s for s in listed}
    regime = current_regime(index)
    hits = scan_satellite(stocks, index, meta) if regime.risk_on else []
    lines = [
        f"# NEPSE strategy scan — {regime.date}",
        "",
        f"**{regime.reason}**",
        "",
        f"NEPSE {regime.close:.2f} · RSI {regime.rsi:.1f} · 200 EMA {regime.ema200:.2f}",
        "",
    ]
    if not regime.risk_on:
        lines += ["Core: **cash**. No new satellite buys.", ""]
    else:
        lines += [
            f"Core: **hold NEPSE** (~{int(CORE_ALLOC*100)}% of book).",
            "",
            "## Satellite bounce candidates",
            "",
        ]
        if hits:
            lines += [
                "| Symbol | Name | Close | RSI | RS 63d | Vol/MA | Target +3% | Stop −12% |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
            for h in hits:
                lines.append(
                    f"| {h['symbol']} | {h['name'] or h['symbol']} | {h['close']:.2f} | {h['rsi']:.1f} | "
                    f"{h['rs_63'] if h['rs_63'] is not None else '—'}% | "
                    f"{h['vol_x'] if h['vol_x'] is not None else '—'}× | {h['target']:.2f} | {h['stop']:.2f} |"
                )
        else:
            lines.append("None today.")
        lines.append("")
    lines.append("_Not financial advice._")
    text = "\n".join(lines) + "\n"
    payload = {"regime": asdict(regime), "satellite": hits, "message": text}
    print(text)
    if persist:
        cs.save_json(SCAN_FILE, payload)
        print(f"Saved {SCAN_FILE}")
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="NEPSE barbell strategy (index RSI cycle + bounce overlay)")
    p.add_argument("--backtest", action="store_true", help="Train/test report vs NEPSE")
    p.add_argument("--scan", action="store_true", help="Today's regime + satellite names")
    p.add_argument("--no-persist", action="store_true")
    args = p.parse_args(argv)
    persist = not args.no_persist
    if args.scan and not args.backtest:
        run_scan(persist=persist)
        return 0
    run_backtest(persist=persist)
    if args.scan:
        run_scan(persist=persist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
