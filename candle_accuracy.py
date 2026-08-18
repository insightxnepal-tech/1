#!/usr/bin/env python3
"""
Monthly accuracy report for the NEPSE 200/20 EMA candle buy/sell script.

Replays the same ENTRY / EXIT rules as candle_scanner.py across historical
daily bars for every ordinary equity, then scores:

  BUY  — after an ENTRY, was the close higher 1 / 5 / 10 / 20 sessions later?
  SELL — when EXIT fired, was the paper trade green, and did price fall after?

Fills match the live paper book: entry and exit at the signal-bar close
(the daily scan runs after the close). Not financial advice.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

import pandas as pd

import candle_scanner as cs

HORIZONS = (1, 5, 10, 20)
ACCURACY_REPORT = os.getenv("CANDLE_ACCURACY_REPORT", "candle_accuracy_monthly.md")
ACCURACY_JSON = os.getenv("CANDLE_ACCURACY_JSON", "candle_accuracy_monthly.json")
ACCURACY_TRADES = os.getenv("CANDLE_ACCURACY_TRADES", "candle_accuracy_trades.csv")
OHLCV_CACHE_DIR = os.getenv("CANDLE_OHLCV_CACHE", "data/ohlcv")
HISTORY_CALENDAR_DAYS = int(os.getenv("CANDLE_ACCURACY_DAYS", "1600"))


@dataclass
class BuyEvent:
    symbol: str
    date: str
    close: float
    ret_1d: Optional[float] = None
    ret_5d: Optional[float] = None
    ret_10d: Optional[float] = None
    ret_20d: Optional[float] = None
    name: str = ""
    sector: str = ""


@dataclass
class SellEvent:
    symbol: str
    date: str
    close: float
    entry_date: str
    entry_price: float
    pnl_pct: float
    hold_days: int
    reasons: list[str] = field(default_factory=list)
    post_5d: Optional[float] = None
    post_10d: Optional[float] = None
    name: str = ""
    sector: str = ""


@dataclass
class Trade:
    symbol: str
    entry_date: str
    exit_date: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    pnl_pct: Optional[float]
    hold_days: Optional[int]
    exit_reasons: list[str] = field(default_factory=list)
    open: bool = False
    name: str = ""
    sector: str = ""


def _pct(n: int, d: int) -> Optional[float]:
    if d <= 0:
        return None
    return round(100.0 * n / d, 1)


def _avg(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _fmt_pct(value: Optional[float], signed: bool = False) -> str:
    if value is None:
        return "—"
    if signed:
        return f"{value:+.1f}%"
    return f"{value:.1f}%"


def _month_key(date_str: str) -> str:
    return str(date_str)[:7]


def _month_label(key: str) -> str:
    try:
        dt = datetime.strptime(key + "-01", "%Y-%m-%d")
        return dt.strftime("%b %Y")
    except ValueError:
        return key


def _horizon_return(closes: pd.Series, idx: int, n: int) -> Optional[float]:
    j = idx + n
    if j >= len(closes):
        return None
    base = float(closes.iloc[idx])
    if base <= 0:
        return None
    later = float(closes.iloc[j])
    if pd.isna(later):
        return None
    return (later / base - 1.0) * 100.0


def _classify_exit(reasons: list[str]) -> str:
    text = " ".join(reasons).lower()
    if "overbought" in text:
        return "rsi70"
    if "200 ema" in text:
        return "below200"
    if "20 ema" in text:
        return "below20"
    return "other"


def replay_symbol(
    indicated: pd.DataFrame,
    symbol: str,
    name: str = "",
    sector: str = "",
) -> tuple[list[Trade], list[BuyEvent], list[SellEvent]]:
    """Walk one indicated OHLCV frame with the live paper ENTRY/EXIT rules."""
    trades: list[Trade] = []
    buys: list[BuyEvent] = []
    sells: list[SellEvent] = []
    if indicated is None or len(indicated) < cs.MIN_HISTORY:
        return trades, buys, sells

    needed = {"ema20", "ema200", "rsi", "vol_ma20"}
    if not needed.issubset(indicated.columns):
        indicated = cs.compute_indicators(indicated)

    closes = indicated["close"].astype(float)
    held = False
    entry_idx: Optional[int] = None
    entry_price = 0.0
    entry_date = ""

    for i in range(cs.MIN_HISTORY - 1, len(indicated)):
        sig = cs.evaluate_bar(indicated, i, symbol)
        if sig is None:
            continue
        action = cs.apply_position_rules(
            sig,
            {symbol: {"entry_price": entry_price, "entry_date": entry_date}} if held else {},
        )
        if action == "ENTRY":
            held = True
            entry_idx = i
            entry_price = float(sig.close)
            entry_date = sig.date
            buys.append(
                BuyEvent(
                    symbol=symbol,
                    date=sig.date,
                    close=float(sig.close),
                    ret_1d=_horizon_return(closes, i, 1),
                    ret_5d=_horizon_return(closes, i, 5),
                    ret_10d=_horizon_return(closes, i, 10),
                    ret_20d=_horizon_return(closes, i, 20),
                    name=name,
                    sector=sector,
                )
            )
        elif action == "EXIT" and held and entry_idx is not None:
            pnl = (float(sig.close) - entry_price) / entry_price * 100.0 if entry_price else 0.0
            hold_days = i - entry_idx
            sells.append(
                SellEvent(
                    symbol=symbol,
                    date=sig.date,
                    close=float(sig.close),
                    entry_date=entry_date,
                    entry_price=entry_price,
                    pnl_pct=round(pnl, 2),
                    hold_days=hold_days,
                    reasons=list(sig.exit_reasons),
                    post_5d=_horizon_return(closes, i, 5),
                    post_10d=_horizon_return(closes, i, 10),
                    name=name,
                    sector=sector,
                )
            )
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_date=entry_date,
                    exit_date=sig.date,
                    entry_price=round(entry_price, 2),
                    exit_price=float(sig.close),
                    pnl_pct=round(pnl, 2),
                    hold_days=hold_days,
                    exit_reasons=list(sig.exit_reasons),
                    open=False,
                    name=name,
                    sector=sector,
                )
            )
            held = False
            entry_idx = None

    if held and entry_idx is not None:
        last_px = float(closes.iloc[-1])
        pnl = (last_px - entry_price) / entry_price * 100.0 if entry_price else 0.0
        last_date = indicated["businessDate"].iloc[-1]
        if hasattr(last_date, "strftime"):
            last_str = last_date.strftime("%Y-%m-%d")
        else:
            last_str = str(last_date)[:10]
        trades.append(
            Trade(
                symbol=symbol,
                entry_date=entry_date,
                exit_date=None,
                entry_price=round(entry_price, 2),
                exit_price=round(last_px, 2),
                pnl_pct=round(pnl, 2),
                hold_days=len(indicated) - 1 - entry_idx,
                exit_reasons=[],
                open=True,
                name=name,
                sector=sector,
            )
        )

    return trades, buys, sells


def replay_universe(
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    meta: Optional[dict[str, cs.ListedScript]] = None,
) -> tuple[list[Trade], list[BuyEvent], list[SellEvent], int]:
    meta = meta or {}
    trades: list[Trade] = []
    buys: list[BuyEvent] = []
    sells: list[SellEvent] = []
    skipped = 0
    for symbol, raw in sorted(ohlcv_by_symbol.items()):
        if raw is None or len(raw) < cs.MIN_HISTORY:
            skipped += 1
            continue
        info = meta.get(symbol)
        name = info.name if info else ""
        sector = info.sector if info else ""
        try:
            indicated = raw if {"ema20", "ema200", "rsi"}.issubset(raw.columns) else cs.compute_indicators(raw)
            t, b, s = replay_symbol(indicated, symbol, name=name, sector=sector)
        except Exception as e:
            print(f"  {symbol}: replay error {e}")
            skipped += 1
            continue
        trades.extend(t)
        buys.extend(b)
        sells.extend(s)
    return trades, buys, sells, skipped


def _win_stats(returns: list[Optional[float]]) -> tuple[Optional[float], Optional[float], int]:
    known = [r for r in returns if r is not None]
    if not known:
        return None, None, 0
    wins = sum(1 for r in known if r > 0)
    return _pct(wins, len(known)), _avg(known), len(known)


def _empty_month_row(month: str) -> dict:
    return {
        "month": month,
        "label": _month_label(month),
        "buy_signals": 0,
        "buy_win_1d": None,
        "buy_win_5d": None,
        "buy_win_10d": None,
        "buy_win_20d": None,
        "buy_avg_1d": None,
        "buy_avg_5d": None,
        "buy_avg_10d": None,
        "buy_avg_20d": None,
        "buy_n_1d": 0,
        "buy_n_5d": 0,
        "buy_n_10d": 0,
        "buy_n_20d": 0,
        "sell_signals": 0,
        "sell_win_pct": None,
        "sell_avg_pnl": None,
        "sell_avg_hold": None,
        "sell_lower_5d": None,
        "sell_avg_post_5d": None,
        "sell_n_post_5d": 0,
        "exit_rsi70": 0,
        "exit_below20": 0,
        "exit_below200": 0,
        "closed_trades": 0,
        "open_trades": 0,
    }


def aggregate_monthly(
    buys: list[BuyEvent],
    sells: list[SellEvent],
    trades: Optional[list[Trade]] = None,
) -> list[dict]:
    """One row per calendar month that had a buy or a sell."""
    months: dict[str, dict] = {}

    def row_for(date_str: str) -> dict:
        key = _month_key(date_str)
        if key not in months:
            months[key] = _empty_month_row(key)
        return months[key]

    buys_by_month: dict[str, list[BuyEvent]] = defaultdict(list)
    for b in buys:
        buys_by_month[_month_key(b.date)].append(b)
        row_for(b.date)

    sells_by_month: dict[str, list[SellEvent]] = defaultdict(list)
    for s in sells:
        sells_by_month[_month_key(s.date)].append(s)
        row_for(s.date)

    if trades:
        for t in trades:
            if t.open:
                row_for(t.entry_date)["open_trades"] += 1
            else:
                row_for(t.exit_date or t.entry_date)["closed_trades"] += 1

    for key, group in buys_by_month.items():
        row = months[key]
        row["buy_signals"] = len(group)
        for n in HORIZONS:
            attr = f"ret_{n}d"
            win, avg, count = _win_stats([getattr(b, attr) for b in group])
            row[f"buy_win_{n}d"] = win
            row[f"buy_avg_{n}d"] = avg
            row[f"buy_n_{n}d"] = count

    for key, group in sells_by_month.items():
        row = months[key]
        row["sell_signals"] = len(group)
        wins = sum(1 for s in group if s.pnl_pct > 0)
        row["sell_win_pct"] = _pct(wins, len(group))
        row["sell_avg_pnl"] = _avg([s.pnl_pct for s in group])
        row["sell_avg_hold"] = _avg([float(s.hold_days) for s in group])
        lower, post_avg, post_n = _win_stats(
            [(-s.post_5d if s.post_5d is not None else None) for s in group]
        )
        # lower 5d later = post_5d < 0. Reuse win_stats by negating.
        row["sell_lower_5d"] = lower
        row["sell_avg_post_5d"] = _avg([s.post_5d for s in group if s.post_5d is not None])
        row["sell_n_post_5d"] = post_n
        for s in group:
            kind = _classify_exit(s.reasons)
            if kind == "rsi70":
                row["exit_rsi70"] += 1
            elif kind == "below200":
                row["exit_below200"] += 1
            elif kind == "below20":
                row["exit_below20"] += 1

    return [months[k] for k in sorted(months)]


def summarize(buys: list[BuyEvent], sells: list[SellEvent], trades: list[Trade]) -> dict:
    closed = [t for t in trades if not t.open]
    closed_wins = sum(1 for t in closed if (t.pnl_pct or 0) > 0)
    buy_win_5d, buy_avg_5d, buy_n_5d = _win_stats([b.ret_5d for b in buys])
    buy_win_10d, buy_avg_10d, buy_n_10d = _win_stats([b.ret_10d for b in buys])
    buy_win_20d, buy_avg_20d, buy_n_20d = _win_stats([b.ret_20d for b in buys])
    buy_win_1d, buy_avg_1d, buy_n_1d = _win_stats([b.ret_1d for b in buys])
    sell_win = _pct(sum(1 for s in sells if s.pnl_pct > 0), len(sells))
    lower_5d, _, _ = _win_stats([(-s.post_5d if s.post_5d is not None else None) for s in sells])
    return {
        "buy_signals": len(buys),
        "sell_signals": len(sells),
        "closed_trades": len(closed),
        "open_trades": sum(1 for t in trades if t.open),
        "trade_win_pct": _pct(closed_wins, len(closed)),
        "trade_avg_pnl": _avg([t.pnl_pct for t in closed if t.pnl_pct is not None]),
        "trade_avg_hold": _avg([float(t.hold_days) for t in closed if t.hold_days is not None]),
        "buy_win_1d": buy_win_1d,
        "buy_avg_1d": buy_avg_1d,
        "buy_n_1d": buy_n_1d,
        "buy_win_5d": buy_win_5d,
        "buy_avg_5d": buy_avg_5d,
        "buy_n_5d": buy_n_5d,
        "buy_win_10d": buy_win_10d,
        "buy_avg_10d": buy_avg_10d,
        "buy_n_10d": buy_n_10d,
        "buy_win_20d": buy_win_20d,
        "buy_avg_20d": buy_avg_20d,
        "buy_n_20d": buy_n_20d,
        "sell_win_pct": sell_win,
        "sell_avg_pnl": _avg([s.pnl_pct for s in sells]),
        "sell_lower_5d": lower_5d,
        "sell_avg_post_5d": _avg([s.post_5d for s in sells if s.post_5d is not None]),
    }


def format_monthly_report(
    rows: list[dict],
    summary: dict,
    *,
    as_of: str,
    scanned: int,
    skipped: int,
    first_bar: str,
    last_bar: str,
) -> str:
    lines = [
        f"# NEPSE candle buy/sell accuracy — monthly",
        "",
        f"History window: **{first_bar}** → **{last_bar}** (as of {as_of}).",
        f"Ordinary equities replayed: **{scanned}** (skipped thin/no data: {skipped}).",
        "",
        "Same rules as the daily scanner:",
        "",
        "- **BUY / ENTRY** — close > 200 EMA, RSI(14) 38–48 dip (this bar or prior two, RSI still ≤ 55), green bounce near 20 EMA, volume > 20-day MA.",
        "- **SELL / EXIT** (open paper position only) — close below 20 EMA, close below 200 EMA, or RSI ≥ 70.",
        "",
        "Fill: signal-bar **close** (matches the live paper book; the scan runs after the close).",
        "Buy accuracy = % of ENTRYs whose close was **higher** N sessions later.",
        "Sell accuracy = % of EXITs that closed a **green** paper trade, plus how often price was **lower 5 sessions after** the sell.",
        "",
        "## Monthly accuracy",
        "",
        "| Month | Buys | Buy 1d | Buy 5d | Buy 10d | Buy 20d | Avg 5d | Avg 10d | Sells | Sell win | Avg P/L | Avg hold | Lower 5d later |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            "| {label} | {buy_signals} | {buy_win_1d} | {buy_win_5d} | {buy_win_10d} | {buy_win_20d} | {buy_avg_5d} | {buy_avg_10d} | {sell_signals} | {sell_win_pct} | {sell_avg_pnl} | {hold} | {lower} |".format(
                label=r["label"],
                buy_signals=r["buy_signals"],
                buy_win_1d=_fmt_pct(r["buy_win_1d"]),
                buy_win_5d=_fmt_pct(r["buy_win_5d"]),
                buy_win_10d=_fmt_pct(r["buy_win_10d"]),
                buy_win_20d=_fmt_pct(r["buy_win_20d"]),
                buy_avg_5d=_fmt_pct(r["buy_avg_5d"], signed=True),
                buy_avg_10d=_fmt_pct(r["buy_avg_10d"], signed=True),
                sell_signals=r["sell_signals"],
                sell_win_pct=_fmt_pct(r["sell_win_pct"]),
                sell_avg_pnl=_fmt_pct(r["sell_avg_pnl"], signed=True),
                hold="—" if r["sell_avg_hold"] is None else f"{r['sell_avg_hold']:.1f}d",
                lower=_fmt_pct(r["sell_lower_5d"]),
            )
        )

    lines += [
        "",
        f"**All months:** {summary['buy_signals']} buys · "
        f"1d {_fmt_pct(summary['buy_win_1d'])} · "
        f"5d {_fmt_pct(summary['buy_win_5d'])} "
        f"({_fmt_pct(summary['buy_avg_5d'], signed=True)}) · "
        f"10d {_fmt_pct(summary['buy_win_10d'])} "
        f"({_fmt_pct(summary['buy_avg_10d'], signed=True)}) · "
        f"20d {_fmt_pct(summary['buy_win_20d'])} "
        f"({_fmt_pct(summary['buy_avg_20d'], signed=True)}) · "
        f"{summary['sell_signals']} sells · "
        f"win {_fmt_pct(summary['sell_win_pct'])} · "
        f"avg P/L {_fmt_pct(summary['trade_avg_pnl'], signed=True)} · "
        f"avg hold {summary['trade_avg_hold'] if summary['trade_avg_hold'] is not None else '—'}d · "
        f"open {summary['open_trades']}.",
        "",
        "## Monthly buy detail",
        "",
        "| Month | Buy signals | 1d win (n) | 5d win (n) | 10d win (n) | 20d win (n) | Avg 1d | Avg 5d | Avg 10d | Avg 20d |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            "| {label} | {buy_signals} | {w1} ({n1}) | {w5} ({n5}) | {w10} ({n10}) | {w20} ({n20}) | {a1} | {a5} | {a10} | {a20} |".format(
                label=r["label"],
                buy_signals=r["buy_signals"],
                w1=_fmt_pct(r["buy_win_1d"]),
                n1=r["buy_n_1d"],
                w5=_fmt_pct(r["buy_win_5d"]),
                n5=r["buy_n_5d"],
                w10=_fmt_pct(r["buy_win_10d"]),
                n10=r["buy_n_10d"],
                w20=_fmt_pct(r["buy_win_20d"]),
                n20=r["buy_n_20d"],
                a1=_fmt_pct(r["buy_avg_1d"], signed=True),
                a5=_fmt_pct(r["buy_avg_5d"], signed=True),
                a10=_fmt_pct(r["buy_avg_10d"], signed=True),
                a20=_fmt_pct(r["buy_avg_20d"], signed=True),
            )
        )

    lines += [
        "",
        "## Monthly sell detail",
        "",
        "| Month | Sells | Green-trade win | Avg P/L | Avg hold | Lower 5d later | Avg 5d after | RSI ≥ 70 | Below 20 EMA | Below 200 EMA |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            "| {label} | {sell_signals} | {win} | {pnl} | {hold} | {lower} | {post} | {rsi} | {b20} | {b200} |".format(
                label=r["label"],
                sell_signals=r["sell_signals"],
                win=_fmt_pct(r["sell_win_pct"]),
                pnl=_fmt_pct(r["sell_avg_pnl"], signed=True),
                hold="—" if r["sell_avg_hold"] is None else f"{r['sell_avg_hold']:.1f}d",
                lower=_fmt_pct(r["sell_lower_5d"]),
                post=_fmt_pct(r["sell_avg_post_5d"], signed=True),
                rsi=r["exit_rsi70"],
                b20=r["exit_below20"],
                b200=r["exit_below200"],
            )
        )

    lines += [
        "",
        "Notes:",
        "",
        "- A month with buys but no sells means entries were still open at month-end (or later).",
        "- Horizons that run past the last bar are omitted from that win-rate (n is the scored sample).",
        "- One paper position per script; a new ENTRY is not taken until EXIT.",
        "- Unofficial merolagani adjusted OHLCV. Not financial advice.",
        "",
    ]
    return "\n".join(lines)


def _cache_path(symbol: str) -> str:
    return os.path.join(OHLCV_CACHE_DIR, f"{symbol}.csv")


def load_cached_ohlcv(symbol: str) -> pd.DataFrame:
    path = _cache_path(symbol)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["businessDate"])
        return df
    except Exception:
        return pd.DataFrame()


def save_cached_ohlcv(symbol: str, df: pd.DataFrame) -> None:
    os.makedirs(OHLCV_CACHE_DIR, exist_ok=True)
    df.to_csv(_cache_path(symbol), index=False)


def collect_ohlcv_cached(
    symbols: list[str],
    workers: int = cs.MAX_WORKERS,
    calendar_days: int = HISTORY_CALENDAR_DAYS,
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    ohlcv: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in symbols:
        if use_cache:
            cached = load_cached_ohlcv(symbol)
            if cached is not None and not cached.empty:
                ohlcv[symbol] = cached
                continue
        missing.append(symbol)

    print(f"OHLCV cache hit {len(ohlcv)}/{len(symbols)}; fetching {len(missing)}")
    if missing:
        original_days = cs.HISTORY_CALENDAR_DAYS
        try:
            fetched = {}
            total = len(missing)
            done = 0
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _one(sym: str) -> tuple[str, pd.DataFrame]:
                return sym, cs.fetch_symbol_ohlcv(sym, calendar_days=calendar_days)

            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = {pool.submit(_one, sym): sym for sym in missing}
                for fut in as_completed(futures):
                    sym = futures[fut]
                    done += 1
                    try:
                        _, df = fut.result()
                    except Exception as e:
                        print(f"  {sym}: history error {e}")
                        continue
                    if df is not None and not df.empty:
                        fetched[sym] = df
                        if use_cache:
                            save_cached_ohlcv(sym, df)
                    if done % 25 == 0 or done == total:
                        print(f"    Progress: {done}/{total} ({len(fetched)} with data)")
            ohlcv.update(fetched)
        finally:
            cs.HISTORY_CALENDAR_DAYS = original_days
    return ohlcv


def _date_range(ohlcv_by_symbol: dict[str, pd.DataFrame]) -> tuple[str, str]:
    first = None
    last = None
    for df in ohlcv_by_symbol.values():
        if df is None or df.empty:
            continue
        d0 = pd.to_datetime(df["businessDate"]).min()
        d1 = pd.to_datetime(df["businessDate"]).max()
        first = d0 if first is None else min(first, d0)
        last = d1 if last is None else max(last, d1)
    def fmt(d):
        if d is None:
            return "?"
        return pd.Timestamp(d).strftime("%Y-%m-%d")
    return fmt(first), fmt(last)


def write_trades_csv(path: str, trades: list[Trade]) -> None:
    fields = [
        "symbol",
        "name",
        "sector",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "pnl_pct",
        "hold_days",
        "open",
        "exit_reasons",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in trades:
            writer.writerow(
                {
                    "symbol": t.symbol,
                    "name": t.name,
                    "sector": t.sector,
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date or "",
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price if t.exit_price is not None else "",
                    "pnl_pct": t.pnl_pct if t.pnl_pct is not None else "",
                    "hold_days": t.hold_days if t.hold_days is not None else "",
                    "open": t.open,
                    "exit_reasons": "; ".join(t.exit_reasons),
                }
            )


def run_accuracy(
    scan_all: bool = True,
    symbols: Optional[Iterable[str]] = None,
    workers: int = cs.MAX_WORKERS,
    persist: bool = True,
    use_cache: bool = True,
    calendar_days: int = HISTORY_CALENDAR_DAYS,
) -> dict:
    listed: list[cs.ListedScript] = []
    try:
        listed = cs.fetch_listed_scripts()
    except Exception as e:
        print(f"Company list fetch failed ({e}); using {cs.UNIVERSE_FILE} if present")
        raw = cs.load_json(cs.UNIVERSE_FILE, [])
        listed = [cs.ListedScript(**row) for row in raw if isinstance(row, dict) and row.get("symbol")]

    skipped_non_equity = sum(
        1 for s in listed if not cs._is_ordinary_equity(s.symbol, s.name, s.sector)
    )
    universe = cs.resolve_scripts(scan_all=scan_all, only=symbols, listed=listed)
    meta = {s.symbol: s for s in listed}
    print(
        f"Accuracy replay: {len(universe)} ordinary scripts "
        f"({len(listed)} listed, {skipped_non_equity} non-equity skipped)"
    )

    ohlcv = collect_ohlcv_cached(
        [s.symbol for s in universe],
        workers=workers,
        calendar_days=calendar_days,
        use_cache=use_cache,
    )
    trades, buys, sells, skipped = replay_universe(ohlcv, meta)
    rows = aggregate_monthly(buys, sells, trades)
    summary = summarize(buys, sells, trades)
    first_bar, last_bar = _date_range(ohlcv)
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report = format_monthly_report(
        rows,
        summary,
        as_of=as_of,
        scanned=len(ohlcv) - skipped,
        skipped=skipped + (len(universe) - len(ohlcv)),
        first_bar=first_bar,
        last_bar=last_bar,
    )
    print(report)

    payload = {
        "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_bar": first_bar,
        "last_bar": last_bar,
        "listed": len(listed),
        "universe": len(universe),
        "skipped_non_equity": skipped_non_equity,
        "scanned": len(ohlcv) - skipped,
        "skipped": skipped + (len(universe) - len(ohlcv)),
        "summary": summary,
        "months": rows,
        "buy_events": [asdict(b) for b in buys],
        "sell_events": [asdict(s) for s in sells],
        "open_trades": [asdict(t) for t in trades if t.open],
        "report": report,
    }

    if persist:
        slim = {k: v for k, v in payload.items() if k not in {"buy_events", "sell_events", "report"}}
        slim["buy_events"] = payload["buy_events"]
        slim["sell_events"] = payload["sell_events"]
        cs.save_json(ACCURACY_JSON, slim)
        with open(ACCURACY_REPORT, "w") as f:
            f.write(report)
        write_trades_csv(ACCURACY_TRADES, trades)
        print(f"Saved {ACCURACY_REPORT}, {ACCURACY_JSON}, {ACCURACY_TRADES}")

    return payload


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Monthly accuracy of the NEPSE candle buy/sell script")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols (default: all ordinary equities)")
    parser.add_argument("--workers", type=int, default=cs.MAX_WORKERS)
    parser.add_argument("--no-cache", action="store_true", help="Refetch OHLCV even if data/ohlcv/*.csv exists")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--days", type=int, default=HISTORY_CALENDAR_DAYS, help="Calendar days of merolagani history")
    args = parser.parse_args(argv)
    only = [s for s in args.symbols.split(",") if s.strip()] or None
    run_accuracy(
        scan_all=only is None,
        symbols=only,
        workers=args.workers,
        persist=not args.no_persist,
        use_cache=not args.no_cache,
        calendar_days=args.days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
