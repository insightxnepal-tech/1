#!/usr/bin/env python3
"""Unit tests for the daily 200/20 EMA candle scanner (no NEPSE network)."""

import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import candle_scanner as cs


SAMPLE_COMPANY_HTML = """
<a data-toggle="collapse" href="#collapse_1">Commercial Banks</a>
<table>
<tr>
<td class="text-left">
<a href='/CompanyDetail.aspx?symbol=NABIL'>NABIL</a>
</td>
<td class="text-left">Nabil Bank Limited</td>
</tr>
<tr>
<td class="text-left">
<a href='/CompanyDetail.aspx?symbol=NABILP'>NABILP</a>
</td>
<td class="text-left">Nabil Bank Limited Promoter Share</td>
</tr>
</table>
<a data-toggle="collapse" href="#collapse_2">Mutual Fund</a>
<table>
<tr>
<td class="text-left">
<a href='/CompanyDetail.aspx?symbol=NIBSF1'>NIBSF1</a>
</td>
<td class="text-left">NIBL Samriddhi Fund 1</td>
</tr>
</table>
<a data-toggle="collapse" href="#collapse_3">Corporate Debenture</a>
<table>
<tr>
<td class="text-left">
<a href='/CompanyDetail.aspx?symbol=ADBLD83'>ADBLD83</a>
</td>
<td class="text-left">10.35% Agricultural Bank Debenture 2083</td>
</tr>
</table>
"""


def make_ohlcv(
    n=240,
    start_price=100.0,
    trend=0.15,
    bounce=True,
    rsi_zone=True,
    green=True,
    high_volume=True,
    below_200=False,
    far_from_20=False,
    red_below_20=False,
    overbought=False,
):
    """Build a synthetic daily series that can satisfy or break each rule."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2025-01-01", periods=n)
    t = np.linspace(0, 1, n)
    close = start_price * (1 + trend * t)
    close = close + rng.normal(0, 0.15, n)
    if below_200:
        close[-40:] = close[-40:] * 0.82
    close = np.maximum(close, 1.0)

    s = pd.Series(close)
    ema20 = s.ewm(span=20, adjust=False).mean()
    ema200 = s.ewm(span=200, adjust=False).mean()

    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.4
    low = np.minimum(open_, close) - 0.4
    volume = np.full(n, 10_000.0)

    ema20_last = float(ema20.iloc[-2])
    ema200_last = float(ema200.iloc[-1])

    if red_below_20:
        close[-1] = ema20_last * 0.97
        open_[-1] = close[-1] * 1.02
        high[-1] = open_[-1]
        low[-1] = close[-1] * 0.99
    elif far_from_20:
        close[-1] = ema20_last * 1.08
        open_[-1] = close[-1] * 0.99
        high[-1] = close[-1] * 1.01
        low[-1] = open_[-1]
    elif green:
        close[-1] = ema20_last * 1.004
        open_[-1] = ema20_last * 0.992
        low[-1] = ema20_last * 0.995
        high[-1] = close[-1] * 1.005
        if below_200:
            close[-1] = ema200_last * 0.97
            open_[-1] = close[-1] * 0.99
            low[-1] = close[-1] * 0.98
            high[-1] = open_[-1] * 1.01
    else:
        close[-1] = ema20_last * 1.002
        open_[-1] = ema20_last * 1.012
        high[-1] = open_[-1]
        low[-1] = ema20_last * 0.995

    if high_volume:
        volume[-1] = 25_000
    else:
        volume[-1] = 1_000

    df = pd.DataFrame(
        {
            "businessDate": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )

    indicated = cs.compute_indicators(df)

    if rsi_zone:
        indicated.loc[indicated.index[-3:], "rsi"] = [46.0, 42.0, 44.0]
    elif overbought:
        indicated.loc[indicated.index[-3:], "rsi"] = [68.0, 71.0, 73.0]
    else:
        indicated.loc[indicated.index[-3:], "rsi"] = [62.0, 61.0, 60.0]

    if bounce is False and not far_from_20 and not red_below_20:
        last = indicated.index[-1]
        indicated.loc[last, "open"] = indicated.loc[last, "ema20"] * 1.06
        indicated.loc[last, "low"] = indicated.loc[last, "ema20"] * 1.05
        indicated.loc[last, "close"] = indicated.loc[last, "ema20"] * 1.07
        indicated.loc[last, "high"] = indicated.loc[last, "close"] * 1.01

    return indicated


class TestIndicators(unittest.TestCase):
    def test_ema_and_rsi_columns(self):
        df = pd.DataFrame(
            {
                "businessDate": pd.bdate_range("2025-01-01", periods=220),
                "high": np.linspace(101, 121, 220),
                "low": np.linspace(99, 119, 220),
                "close": np.linspace(100, 120, 220),
                "volume": np.full(220, 5000),
            }
        )
        out = cs.compute_indicators(df)
        for col in ("ema20", "ema200", "rsi", "vol_ma20", "atr", "open"):
            self.assertIn(col, out.columns)
        self.assertGreater(out["ema200"].iloc[-1], out["ema200"].iloc[50])
        self.assertTrue((out["rsi"].iloc[20:] >= 0).all())
        self.assertTrue((out["rsi"].iloc[20:] <= 100).all())

    def test_open_falls_back_to_previous_close(self):
        df = pd.DataFrame(
            {
                "businessDate": pd.bdate_range("2025-01-01", periods=5),
                "high": [11, 12, 13, 14, 15],
                "low": [9, 10, 11, 12, 13],
                "close": [10, 11, 12, 13, 14],
                "volume": [100] * 5,
            }
        )
        out = cs.compute_indicators(df)
        self.assertAlmostEqual(out["open"].iloc[1], 10)
        self.assertAlmostEqual(out["open"].iloc[-1], 13)


class TestEntryRules(unittest.TestCase):
    def test_all_four_yes_is_entry(self):
        df = make_ohlcv()
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertIsNotNone(sig)
        self.assertTrue(sig.above_200, "price should be above 200 EMA")
        self.assertTrue(sig.rsi_dip, "RSI should be in 38–48")
        self.assertTrue(sig.green_near_20, "green candle should be near 20 EMA")
        self.assertTrue(sig.volume_ok, "volume should exceed MA20")
        self.assertTrue(sig.entry)
        self.assertEqual(sig.signal, "ENTRY")

    def test_below_200_ema_is_ignored(self):
        df = make_ohlcv(below_200=True)
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertFalse(sig.above_200)
        self.assertFalse(sig.entry)

    def test_rsi_lookback_still_counts_as_dip(self):
        df = make_ohlcv()
        df.loc[df.index[-3:], "rsi"] = [41.0, 46.0, 48.2]
        sig = cs.evaluate_latest(df, "API")
        self.assertTrue(sig.rsi_dip)
        self.assertTrue(sig.entry)

    def test_rsi_not_in_zone_is_ignored(self):
        df = make_ohlcv(rsi_zone=False)
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertFalse(sig.rsi_dip)
        self.assertFalse(sig.entry)

    def test_red_candle_is_ignored(self):
        df = make_ohlcv(green=False)
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertFalse(sig.green_near_20)
        self.assertFalse(sig.entry)

    def test_candle_far_from_20_ema_is_ignored(self):
        df = make_ohlcv(far_from_20=True, bounce=False)
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertFalse(sig.green_near_20)
        self.assertFalse(sig.entry)

    def test_low_volume_is_ignored(self):
        df = make_ohlcv(high_volume=False)
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertFalse(sig.volume_ok)
        self.assertFalse(sig.entry)

    def test_too_short_history_returns_none(self):
        df = make_ohlcv(n=50)
        self.assertIsNone(cs.evaluate_latest(df, "NABIL"))


class TestExitAndPositions(unittest.TestCase):
    def test_close_below_20_is_exit_for_open_position(self):
        df = make_ohlcv(red_below_20=True, rsi_zone=False)
        sig = cs.evaluate_latest(df, "JBBL")
        self.assertFalse(sig.entry)
        self.assertTrue(any("20 EMA" in r for r in sig.exit_reasons))
        action = cs.apply_position_rules(sig, {"JBBL": {"entry_price": 400}})
        self.assertEqual(action, "EXIT")

    def test_no_exit_without_open_position(self):
        df = make_ohlcv(red_below_20=True, rsi_zone=False)
        sig = cs.evaluate_latest(df, "JBBL")
        action = cs.apply_position_rules(sig, {})
        self.assertEqual(action, "NONE")

    def test_duplicate_entry_not_refired(self):
        df = make_ohlcv()
        sig = cs.evaluate_latest(df, "NABIL")
        self.assertTrue(sig.entry)
        action = cs.apply_position_rules(sig, {"NABIL": {"entry_price": sig.close}})
        self.assertEqual(action, "NONE")

    def test_rsi_overbought_exits_open_position(self):
        df = make_ohlcv(rsi_zone=False, overbought=True, far_from_20=True)
        sig = cs.evaluate_latest(df, "SBI")
        self.assertTrue(any("overbought" in r.lower() for r in sig.exit_reasons))
        action = cs.apply_position_rules(sig, {"SBI": {"entry_price": 300}})
        self.assertEqual(action, "EXIT")

    def test_update_positions_add_and_remove(self):
        df = make_ohlcv()
        sig = cs.evaluate_latest(df, "GBIME")
        pos = cs.update_positions({}, sig, "ENTRY")
        self.assertIn("GBIME", pos)
        self.assertEqual(pos["GBIME"]["entry_price"], sig.close)
        pos = cs.update_positions(pos, sig, "EXIT")
        self.assertNotIn("GBIME", pos)

    def test_scan_map_emits_entry_then_exit(self):
        entry_df = make_ohlcv()
        exit_df = make_ohlcv(red_below_20=True, rsi_zone=False)
        entries, exits, pos, skipped = cs.scan_ohlcv_map({"HDL": entry_df}, {})
        self.assertEqual(skipped, 0)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].symbol, "HDL")
        self.assertIn("HDL", pos)

        entries2, exits2, pos2, _ = cs.scan_ohlcv_map({"HDL": exit_df}, pos)
        self.assertEqual(len(entries2), 0)
        self.assertEqual(len(exits2), 1)
        self.assertNotIn("HDL", pos2)


class TestTelegramFormatting(unittest.TestCase):
    def test_message_contains_entry_and_exit_headers(self):
        df = make_ohlcv()
        entry = cs.evaluate_latest(df, "NABIL")
        exit_sig = cs.evaluate_latest(make_ohlcv(red_below_20=True, rsi_zone=False), "JBBL")
        msg = cs.format_telegram(
            [entry],
            [(exit_sig, {"entry_price": 400.0, "entry_date": "2026-07-01"})],
            scanned=2,
            as_of="2026-08-16",
        )
        self.assertIn("ENTRY FOUND", msg)
        self.assertIn("EXIT FOUND", msg)
        self.assertIn("NABIL", msg)
        self.assertIn("JBBL", msg)
        self.assertIn("P/L", msg)

    def test_near_misses_are_listed(self):
        df = make_ohlcv()
        entry = cs.evaluate_latest(df, "NABIL")
        miss = cs.evaluate_latest(make_ohlcv(high_volume=False), "LSL")
        msg = cs.format_telegram(
            [entry], [], scanned=2, as_of="2026-08-16", near_misses=[miss]
        )
        self.assertIn("NEAR MISS", msg)
        self.assertIn("LSL", msg)
        self.assertIn("volume", msg.lower())

    def test_empty_scan_still_mentions_entry_and_exit(self):
        msg = cs.format_telegram([], [], scanned=10, as_of="2026-08-16", skipped=2)
        self.assertIn("ENTRY FOUND:* none", msg)
        self.assertIn("EXIT FOUND:* none", msg)


class TestHistoryParser(unittest.TestCase):
    def test_renames_nepse_fields(self):
        rows = [
            {
                "businessDate": "2026-08-14",
                "closePrice": 100,
                "highPrice": 102,
                "lowPrice": 99,
                "openPrice": 98,
                "totalTradedQuantity": 5000,
            },
            {
                "businessDate": "2026-08-15",
                "closePrice": 101,
                "highPrice": 103,
                "lowPrice": 100,
                "openPrice": 100,
                "totalTradedQuantity": 6000,
            },
        ]
        df = cs.history_to_ohlcv(rows)
        self.assertEqual(list(df["close"]), [100, 101])
        self.assertEqual(list(df["volume"]), [5000, 6000])
        self.assertIn("open", df.columns)

    def test_merolagani_chart_json(self):
        data = {
            "s": "ok",
            "t": [1786900000, 1786986400],
            "o": [100, 101],
            "h": [102, 103],
            "l": [99, 100],
            "c": [101, 102],
            "v": [10, 20],
        }
        df = cs.merolagani_chart_to_ohlcv(data)
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df["close"]), [101, 102])
        self.assertIn("businessDate", df.columns)


class TestUniverse(unittest.TestCase):
    def test_parse_and_filter_ordinary_equity(self):
        listed = cs.parse_company_list_html(SAMPLE_COMPANY_HTML)
        by_symbol = {s.symbol: s for s in listed}
        self.assertIn("NABIL", by_symbol)
        self.assertEqual(by_symbol["NABIL"].sector, "Commercial Banks")
        self.assertTrue(cs._is_ordinary_equity("NABIL", "Nabil Bank Limited"))
        self.assertFalse(cs._is_ordinary_equity("NABILP", "Nabil Bank Limited Promoter Share"))
        self.assertFalse(cs._is_ordinary_equity("NIBSF1", "NIBL Samriddhi Fund 1", "Mutual Fund"))
        ordinary = cs.resolve_scripts(scan_all=True, only=None, listed=listed)
        self.assertEqual([s.symbol for s in ordinary], ["NABIL"])

    def test_markdown_report_lists_entries(self):
        sig = cs.evaluate_latest(make_ohlcv(), "NABIL")
        sig.name = "Nabil Bank Limited"
        sig.sector = "Commercial Banks"
        report = cs.format_markdown_report(
            [sig], [], [sig], scanned=1, skipped=0, as_of="2026-08-16",
            universe_count=1, skipped_non_equity=0,
        )
        self.assertIn("NABIL", report)
        self.assertIn("ENTRY", report)

    def test_telegram_report_lists_matching_setups(self):
        sig = cs.evaluate_latest(make_ohlcv(), "MBL")
        text = cs.format_telegram([sig], [], scanned=251, as_of="2026-08-18")
        self.assertIn("MBL", text)
        self.assertIn("ENTRY FOUND", text)


class TestTelegramConfig(unittest.TestCase):
    def test_default_chat_id(self):
        self.assertTrue(cs.TELEGRAM_CHAT_ID)



class TestJsonRoundtrip(unittest.TestCase):
    def test_load_save_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pos.json")
            old = cs.POSITIONS_FILE
            cs.POSITIONS_FILE = path
            try:
                cs.save_json(path, {"API": {"entry_price": 1}})
                loaded = cs.load_positions()
                self.assertEqual(loaded["API"]["entry_price"], 1)
            finally:
                cs.POSITIONS_FILE = old


if __name__ == "__main__":
    unittest.main()
