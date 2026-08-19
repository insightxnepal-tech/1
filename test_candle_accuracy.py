#!/usr/bin/env python3
"""Unit tests for candle buy/sell monthly accuracy (no NEPSE network)."""

import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import candle_accuracy as ca
import candle_scanner as cs
from test_candle_scanner import make_ohlcv


def quiet_trend(n=280, start="2024-01-01"):
    """Smooth uptrend with RSI/volume that do not fire ENTRY by default."""
    dates = pd.bdate_range(start, periods=n)
    close = np.linspace(100, 140, n)
    open_ = np.r_[close[0], close[:-1]]
    df = pd.DataFrame(
        {
            "businessDate": dates,
            "open": open_,
            "high": np.maximum(open_, close) + 0.3,
            "low": np.minimum(open_, close) - 0.3,
            "close": close,
            "volume": np.full(n, 8_000.0),
        }
    )
    indicated = cs.compute_indicators(df)
    indicated["rsi"] = 60.0
    return indicated


def plant_entry(indicated: pd.DataFrame, idx: int) -> pd.DataFrame:
    out = indicated.copy()
    ema20 = float(out.loc[out.index[idx], "ema20"])
    out.loc[out.index[idx], "open"] = ema20 * 0.992
    out.loc[out.index[idx], "close"] = ema20 * 1.004
    out.loc[out.index[idx], "low"] = ema20 * 0.995
    out.loc[out.index[idx], "high"] = ema20 * 1.01
    out.loc[out.index[idx], "volume"] = 25_000.0
    look = out.index[max(0, idx - 2) : idx + 1]
    out.loc[look, "rsi"] = [46.0, 42.0, 44.0][-len(look) :]
    return out


def plant_exit_below_20(indicated: pd.DataFrame, idx: int) -> pd.DataFrame:
    out = indicated.copy()
    ema20 = float(out.loc[out.index[idx], "ema20"])
    out.loc[out.index[idx], "close"] = ema20 * 0.97
    out.loc[out.index[idx], "open"] = ema20 * 0.99
    out.loc[out.index[idx], "high"] = ema20 * 0.995
    out.loc[out.index[idx], "low"] = ema20 * 0.96
    out.loc[out.index[idx], "rsi"] = 45.0
    return out


class TestEvaluateBar(unittest.TestCase):
    def test_matches_evaluate_latest_on_last_row(self):
        df = make_ohlcv()
        latest = cs.evaluate_latest(df, "NABIL")
        bar = cs.evaluate_bar(df, len(df) - 1, "NABIL")
        self.assertEqual(latest.entry, bar.entry)
        self.assertEqual(latest.date, bar.date)
        self.assertEqual(latest.close, bar.close)
        self.assertEqual(latest.exit_reasons, bar.exit_reasons)

    def test_mid_history_entry_does_not_require_being_last_bar(self):
        df = quiet_trend()
        idx = 220
        df = plant_entry(df, idx)
        mid = cs.evaluate_bar(df, idx, "MBL")
        last = cs.evaluate_latest(df, "MBL")
        self.assertTrue(mid.entry)
        self.assertFalse(last.entry)


class TestReplay(unittest.TestCase):
    def test_one_buy_then_sell_is_one_closed_trade(self):
        df = quiet_trend()
        entry_idx = 220
        exit_idx = 235
        df = plant_entry(df, entry_idx)
        df = plant_exit_below_20(df, exit_idx)
        entry_px = float(df.loc[df.index[entry_idx], "close"])
        # Higher closes after entry so 5d buy is a win; exit still below that bar's 20 EMA.
        for j in range(entry_idx + 1, exit_idx):
            df.loc[df.index[j], "close"] = entry_px * (1 + 0.005 * (j - entry_idx))
        df.loc[df.index[exit_idx], "close"] = entry_px * 1.08
        df.loc[df.index[exit_idx], "open"] = entry_px * 1.09
        df.loc[df.index[exit_idx], "ema20"] = entry_px * 1.12

        trades, buys, sells = ca.replay_symbol(df, "NABIL", name="Nabil", sector="Banks")
        self.assertEqual(len(buys), 1)
        self.assertEqual(len(sells), 1)
        self.assertEqual(len(trades), 1)
        self.assertFalse(trades[0].open)
        self.assertEqual(buys[0].symbol, "NABIL")
        self.assertGreater(sells[0].pnl_pct, 0)
        self.assertEqual(sells[0].hold_days, exit_idx - entry_idx)
        self.assertIsNotNone(buys[0].ret_5d)
        self.assertGreater(buys[0].ret_5d, 0)

    def test_open_trade_marked_when_never_exits(self):
        df = plant_entry(quiet_trend(), 220)
        trades, buys, sells = ca.replay_symbol(df, "SHIVM")
        self.assertEqual(len(buys), 1)
        self.assertEqual(len(sells), 0)
        self.assertEqual(len(trades), 1)
        self.assertTrue(trades[0].open)


class TestMonthlyAggregate(unittest.TestCase):
    def test_tables_split_buy_and_sell_by_month(self):
        buys = [
            ca.BuyEvent("AAA", "2026-01-10", 100, ret_1d=1.0, ret_5d=2.0, ret_10d=-1.0, ret_20d=3.0),
            ca.BuyEvent("BBB", "2026-01-20", 50, ret_1d=-0.5, ret_5d=1.0, ret_10d=1.5, ret_20d=None),
            ca.BuyEvent("CCC", "2026-02-05", 80, ret_1d=0.2, ret_5d=-2.0, ret_10d=-3.0, ret_20d=-4.0),
        ]
        sells = [
            ca.SellEvent("AAA", "2026-02-12", 110, "2026-01-10", 100, 10.0, 20, ["Close below 20 EMA (1)"], post_5d=-1.5),
            ca.SellEvent("DDD", "2026-02-18", 90, "2026-01-15", 100, -10.0, 25, ["RSI overbought (72.0 >= 70)"], post_5d=2.0),
        ]
        trades = [
            ca.Trade("AAA", "2026-01-10", "2026-02-12", 100, 110, 10.0, 20, open=False),
            ca.Trade("DDD", "2026-01-15", "2026-02-18", 100, 90, -10.0, 25, open=False),
            ca.Trade("CCC", "2026-02-05", None, 80, 82, 2.5, 8, open=True),
        ]
        rows = ca.aggregate_monthly(buys, sells, trades)
        self.assertEqual([r["month"] for r in rows], ["2026-01", "2026-02"])
        jan, feb = rows
        self.assertEqual(jan["buy_signals"], 2)
        self.assertEqual(jan["sell_signals"], 0)
        self.assertEqual(jan["buy_win_1d"], 50.0)  # 1 of 2
        self.assertEqual(jan["buy_win_5d"], 100.0)
        self.assertEqual(jan["buy_n_20d"], 1)
        self.assertEqual(feb["buy_signals"], 1)
        self.assertEqual(feb["sell_signals"], 2)
        self.assertEqual(feb["sell_win_pct"], 50.0)
        self.assertEqual(feb["exit_rsi70"], 1)
        self.assertEqual(feb["exit_below20"], 1)
        self.assertEqual(feb["closed_trades"], 2)
        self.assertEqual(feb["open_trades"], 1)
        self.assertEqual(feb["sell_lower_5d"], 50.0)

        summary = ca.summarize(buys, sells, trades)
        self.assertEqual(summary["buy_signals"], 3)
        self.assertEqual(summary["sell_signals"], 2)
        self.assertEqual(summary["trade_win_pct"], 50.0)
        self.assertEqual(summary["open_trades"], 1)

        md = ca.format_monthly_report(
            rows,
            summary,
            as_of="2026-08-18",
            scanned=3,
            skipped=0,
            first_bar="2024-01-02",
            last_bar="2026-08-18",
        )
        self.assertIn("| Jan 2026 |", md)
        self.assertIn("| Feb 2026 |", md)
        self.assertIn("Buy 5d", md)
        self.assertIn("Sell win", md)
        self.assertIn("Monthly buy detail", md)
        self.assertIn("Monthly sell detail", md)

    def test_empty_events_make_empty_table(self):
        self.assertEqual(ca.aggregate_monthly([], [], []), [])


class TestTradesCsv(unittest.TestCase):
    def test_writes_header_and_row(self):
        trades = [
            ca.Trade("MBL", "2026-08-01", "2026-08-10", 250, 255, 2.0, 7, ["RSI overbought (71.0 >= 70)"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "trades.csv")
            ca.write_trades_csv(path, trades)
            with open(path) as f:
                text = f.read()
        self.assertIn("symbol,name,sector,entry_date", text)
        self.assertIn("MBL", text)
        self.assertIn("2.0", text)


if __name__ == "__main__":
    unittest.main()
