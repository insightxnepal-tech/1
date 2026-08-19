#!/usr/bin/env python3
"""Unit tests for the NEPSE barbell strategy (no live trading)."""

import unittest

import numpy as np
import pandas as pd

import nepse_strategy as ns


class TestRsiCycle(unittest.TestCase):
    def test_starts_invested_and_flattens_at_80(self):
        rsi = np.array([50.0, 60.0, 81.0, 70.0, 55.0, 39.0, 50.0])
        pos = ns.rsi_cycle_mask(rsi, sell=80, buy=40)
        self.assertEqual(list(pos), [1, 1, 0, 0, 0, 1, 1])

    def test_stays_cash_until_buy_threshold(self):
        rsi = np.array([82.0, 60.0, 45.0, 41.0, 40.0])
        pos = ns.rsi_cycle_mask(rsi, sell=80, buy=40)
        self.assertEqual(list(pos), [0, 0, 0, 0, 1])

    def test_nan_keeps_prior_state(self):
        rsi = np.array([50.0, np.nan, 81.0])
        pos = ns.rsi_cycle_mask(rsi)
        self.assertEqual(pos[0], 1.0)
        self.assertEqual(pos[1], 1.0)
        self.assertEqual(pos[2], 0.0)


class TestIndexBacktest(unittest.TestCase):
    def test_beats_or_matches_definition_on_synthetic_spike(self):
        n = 40
        close = np.concatenate([np.linspace(100, 120, 20), np.linspace(120, 90, 20)])
        rsi = np.concatenate([np.linspace(50, 85, 20), np.linspace(85, 30, 20)])
        df = pd.DataFrame(
            {
                "close": close,
                "rsi": rsi,
            },
            index=pd.bdate_range("2024-01-01", periods=n),
        )
        out = ns.index_cycle_backtest(df, "2024-01-01", "2024-12-31")
        self.assertIn("strategy_pct", out)
        self.assertIn("nepse_bh_pct", out)
        self.assertTrue(out["cycles_closed"] >= 1)
        self.assertGreater(out["excess_pct"], 0)


class TestSatelliteReplay(unittest.TestCase):
    def test_three_percent_target_is_a_win(self):
        from research_strategies import replay

        n = 40
        dates = pd.bdate_range("2024-06-01", periods=n)
        close = np.full(n, 100.0)
        df = pd.DataFrame(
            {
                "close": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "rsi": np.full(n, 45.0),
            },
            index=dates,
        )
        df.iloc[10, df.columns.get_loc("close")] = 100.0
        df.iloc[15, df.columns.get_loc("high")] = 104.0
        df.iloc[15, df.columns.get_loc("close")] = 103.0
        entry = np.zeros(n, dtype=bool)
        entry[10] = True
        trades = replay(df, entry, tp=0.03, sl=0.12, max_hold=30)
        self.assertEqual(len(trades), 1)
        self.assertGreater(trades[0].pnl_pct, 0)
        self.assertEqual(trades[0].reason, "target")


class TestReportCopy(unittest.TestCase):
    def test_mentions_limits_of_75_percent(self):
        regime = ns.Regime("2026-08-18", 1.0, 50.0, 1.0, True, "RISK-ON")
        sat = {
            "train": {"n": 10, "win": 86.0, "avg": 0.9, "hold": 8},
            "test": {"n": 10, "win": 81.0, "avg": 0.1, "hold": 7},
        }
        core = {
            "start": "2023-02-01",
            "end": "2024-12-31",
            "strategy_pct": 19.9,
            "nepse_bh_pct": 22.7,
            "excess_pct": -2.8,
            "time_in_market_pct": 84.5,
            "cycles_closed": 3,
            "cycle_win_pct": 100.0,
            "cycle_avg_pct": 8.8,
            "trades": [],
        }
        md = ns.format_report(core, core, core, sat, regime)
        self.assertIn("was not found", md)
        self.assertIn("27.5%", md)
        self.assertIn("RSI", md)


if __name__ == "__main__":
    unittest.main()
