"""Unit tests for ATR, volume filter, Supertrend flips, scanner, and reports."""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import config
import data_client as dc
import indicators as ind
import notifier
import scanner
import supertrend as st

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
<a data-toggle="collapse" href="#collapse_3">Hydro Power</a>
<table>
<tr>
<td class="text-left">
<a href='/CompanyDetail.aspx?symbol=HDL'>HDL</a>
</td>
<td class="text-left">Himalayan Distillery Limited</td>
</tr>
</table>
"""


def ohlcv_from_close(
    close: np.ndarray,
    volume: np.ndarray | float = 10_000.0,
    start: str = "2024-01-01",
    spread: float = 1.0,
) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    n = len(close)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    if np.isscalar(volume):
        vol = np.full(n, float(volume))
    else:
        vol = np.asarray(volume, dtype=float)
    dates = pd.bdate_range(start, periods=n)
    return pd.DataFrame(
        {
            "businessDate": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )


def uptrend(n: int = 80, start: float = 100.0, end: float = 180.0) -> pd.DataFrame:
    return ohlcv_from_close(np.linspace(start, end, n), volume=12_000)


def downtrend(n: int = 80, start: float = 180.0, end: float = 100.0) -> pd.DataFrame:
    return ohlcv_from_close(np.linspace(start, end, n), volume=12_000)


class TestIndicators(unittest.TestCase):
    def test_wilder_rma_sma_seed(self):
        values = np.arange(1.0, 11.0)
        rma = ind.wilder_rma(values, 5)
        self.assertTrue(np.isnan(rma[3]))
        self.assertAlmostEqual(rma[4], np.mean(values[:5]))
        expected = (rma[4] * 4 + values[5]) / 5
        self.assertAlmostEqual(rma[5], expected)

    def test_volume_filter_expanding_or_rvol(self):
        self.assertTrue(ind.volume_filter_ok(20_000, 10_000, 1.0, 1.2))
        self.assertTrue(ind.volume_filter_ok(8_000, 10_000, 1.5, 1.2))
        self.assertFalse(ind.volume_filter_ok(8_000, 10_000, 1.1, 1.2))
        self.assertFalse(ind.volume_filter_ok(float("nan"), 10_000, 1.0, 1.2))


class TestSupertrend(unittest.TestCase):
    def test_uptrend_stays_bullish_below_price(self):
        frame = st.compute_supertrend(uptrend())
        last = frame.iloc[-1]
        self.assertEqual(int(last["trend"]), 1)
        self.assertLess(float(last["supertrend"]), float(last["close"]))
        self.assertFalse(bool(last["flip_sell"]))

    def test_downtrend_is_bearish_above_price(self):
        frame = st.compute_supertrend(downtrend())
        last = frame.iloc[-1]
        self.assertEqual(int(last["trend"]), -1)
        self.assertGreater(float(last["supertrend"]), float(last["close"]))

    def test_close_below_green_line_flips_sell(self):
        frame = st.compute_supertrend(uptrend())
        last = frame.iloc[-1]
        crash_close = float(last["supertrend"]) * 0.90
        extra = pd.DataFrame(
            {
                "businessDate": [last["businessDate"] + pd.Timedelta(days=1)],
                "open": [float(last["close"])],
                "high": [float(last["close"])],
                "low": [crash_close * 0.99],
                "close": [crash_close],
                "volume": [12_000],
            }
        )
        combined = pd.concat([uptrend(), extra], ignore_index=True)
        out = st.compute_supertrend(combined)
        bar = out.iloc[-1]
        self.assertTrue(bool(bar["flip_sell"]))
        self.assertEqual(int(bar["trend"]), -1)

    def test_close_above_red_line_flips_buy(self):
        frame = st.compute_supertrend(downtrend())
        last = frame.iloc[-1]
        rally_close = float(last["supertrend"]) * 1.10
        extra = pd.DataFrame(
            {
                "businessDate": [last["businessDate"] + pd.Timedelta(days=1)],
                "open": [float(last["close"])],
                "high": [rally_close * 1.01],
                "low": [float(last["close"])],
                "close": [rally_close],
                "volume": [12_000],
            }
        )
        combined = pd.concat([downtrend(), extra], ignore_index=True)
        out = st.compute_supertrend(combined)
        bar = out.iloc[-1]
        self.assertTrue(bool(bar["flip_buy"]))
        self.assertEqual(int(bar["trend"]), 1)


class TestScannerSignals(unittest.TestCase):
    def test_hold_in_established_uptrend(self):
        row = scanner.evaluate_symbol("HDL", uptrend(90), elite=True)
        self.assertEqual(row.signal, "HOLD")
        self.assertTrue(row.elite)
        self.assertIsNotNone(row.trailing_stop)
        self.assertGreater(row.dist_to_trail_pct, 0)

    def test_sell_on_red_flip(self):
        base = uptrend(90)
        indicated = st.compute_supertrend(base)
        last = indicated.iloc[-1]
        crash = base.copy()
        crash = pd.concat(
            [
                crash,
                pd.DataFrame(
                    {
                        "businessDate": [last["businessDate"] + pd.Timedelta(days=1)],
                        "open": [float(last["close"])],
                        "high": [float(last["close"])],
                        "low": [float(last["supertrend"]) * 0.88],
                        "close": [float(last["supertrend"]) * 0.90],
                        "volume": [12_000],
                    }
                ),
            ],
            ignore_index=True,
        )
        row = scanner.evaluate_symbol("NLG", crash)
        self.assertEqual(row.signal, "SELL")
        self.assertTrue(row.flip_sell)

    def _flip_buy_frame(self, last_volume: float, body_volume: float = 8_000.0) -> pd.DataFrame:
        n = 90
        close = np.linspace(200.0, 110.0, n)
        volume = np.full(n, body_volume)
        volume[-1] = last_volume
        base = ohlcv_from_close(close, volume=volume)
        indicated = st.compute_supertrend(base)
        last = indicated.iloc[-1]
        rally = pd.concat(
            [
                base,
                pd.DataFrame(
                    {
                        "businessDate": [last["businessDate"] + pd.Timedelta(days=1)],
                        "open": [float(last["close"])],
                        "high": [float(last["supertrend"]) * 1.12],
                        "low": [float(last["close"])],
                        "close": [float(last["supertrend"]) * 1.10],
                        "volume": [last_volume],
                    }
                ),
            ],
            ignore_index=True,
        )
        return rally

    def test_buy_requires_volume_filter(self):
        hot = self._flip_buy_frame(last_volume=40_000, body_volume=8_000)
        row = scanner.evaluate_symbol("CIT", hot, elite=True)
        self.assertTrue(row.flip_buy)
        self.assertEqual(row.signal, "BUY")
        self.assertTrue(row.volume_ok)

    def test_green_flip_without_volume_is_blocked(self):
        quiet = self._flip_buy_frame(last_volume=8_000, body_volume=8_000)
        row = scanner.evaluate_symbol("SHEL", quiet)
        self.assertTrue(row.flip_buy)
        self.assertEqual(row.signal, "BLOCKED_BUY")
        self.assertFalse(row.volume_ok)

    def test_elite_always_in_universe_even_if_illiquid(self):
        listed = [
            dc.ListedScript("HDL", "Himalayan Distillery", "Manufacturing"),
            dc.ListedScript("ZZZ", "Thin Name", "Hydro Power"),
        ]
        settings = config.load_settings()
        ohlcv_map = {
            "HDL": ohlcv_from_close(np.linspace(100, 110, 80), volume=100),
            "ZZZ": ohlcv_from_close(np.linspace(100, 110, 80), volume=100),
        }
        universe = scanner.build_universe(listed, ohlcv_map, settings, expand=True)
        symbols = [s.symbol for s in universe]
        self.assertIn("HDL", symbols)
        self.assertNotIn("ZZZ", symbols)

    def test_dynamic_ticker_enters_when_liquid(self):
        listed = [
            dc.ListedScript("HDL", "Himalayan Distillery", "Manufacturing"),
            dc.ListedScript("NABIL", "Nabil Bank Limited", "Commercial Banks"),
        ]
        settings = config.load_settings()
        ohlcv_map = {
            "HDL": uptrend(80),
            "NABIL": ohlcv_from_close(
                np.linspace(400, 450, 80), volume=50_000
            ),
        }
        universe = scanner.build_universe(listed, ohlcv_map, settings, expand=True)
        symbols = [s.symbol for s in universe]
        self.assertIn("NABIL", symbols)

    def test_run_scan_offline_with_injected_ohlcv(self):
        listed = [
            dc.ListedScript("HDL", "Himalayan Distillery", "Manufacturing"),
            dc.ListedScript("NLG", "NLG Insurance", "Non Life Insurance"),
        ]
        ohlcv_map = {"HDL": uptrend(90), "NLG": downtrend(90)}
        report = scanner.run_scan(
            expand=False,
            listed=listed,
            ohlcv_map=ohlcv_map,
        )
        self.assertGreaterEqual(report.scanned, 2)
        hold_symbols = {r.symbol for r in report.holds}
        self.assertIn("HDL", hold_symbols)


class TestDataClient(unittest.TestCase):
    def test_parse_and_filter_ordinary_equity(self):
        listed = dc.parse_company_list_html(SAMPLE_COMPANY_HTML)
        by_symbol = {s.symbol: s for s in listed}
        self.assertIn("NABIL", by_symbol)
        self.assertEqual(by_symbol["NABIL"].sector, "Commercial Banks")
        self.assertTrue(dc.is_ordinary_equity("NABIL", "Nabil Bank Limited"))
        self.assertFalse(
            dc.is_ordinary_equity("NABILP", "Nabil Bank Limited Promoter Share")
        )
        self.assertFalse(
            dc.is_ordinary_equity("NIBSF1", "NIBL Samriddhi Fund 1", "Mutual Fund")
        )

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
        frame = dc.merolagani_chart_to_ohlcv(data)
        self.assertEqual(len(frame), 2)
        self.assertEqual(list(frame["close"]), [101, 102])
        self.assertIn("businessDate", frame.columns)


class TestNotifier(unittest.TestCase):
    def test_telegram_and_markdown_contain_sections(self):
        buy = scanner.evaluate_symbol("HDL", uptrend(90), elite=True)
        buy.signal = "BUY"
        report = scanner.ScanReport(
            strategy=config.STRATEGY_NAME,
            as_of="2026-08-18",
            generated_at="2026-08-18T12:00:00Z",
            universe_count=15,
            elite_count=15,
            dynamic_count=0,
            scanned=15,
            skipped=0,
            data_source="nepse",
            floorsheet_date="2026-08-18",
            floorsheet_rows=1000,
            floorsheet_turnover=1_000_000.0,
            buys=[buy],
        )
        text = notifier.format_telegram(report)
        self.assertIn("HDL", text)
        self.assertIn("BUY", text)
        self.assertIn("floorsheet", text)
        md = notifier.format_markdown_report(report)
        self.assertIn("HDL", md)
        self.assertIn("ACTIVE TREND", md)

    def test_paper_position_round_trip(self):
        buy = scanner.ScanRow(
            symbol="CIT",
            signal="BUY",
            date="2026-08-01",
            close=1000.0,
            trailing_stop=900.0,
        )
        book = scanner.update_positions([buy], {})
        self.assertEqual(book["CIT"]["status"], "OPEN")
        sell = scanner.ScanRow(
            symbol="CIT",
            signal="SELL",
            date="2026-08-18",
            close=1200.0,
            supertrend=1100.0,
        )
        book = scanner.update_positions([sell], book)
        self.assertEqual(book["CIT"]["status"], "CLOSED")
        self.assertAlmostEqual(book["CIT"]["pnl_pct"], 20.0)

    def test_persist_report_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = config.Settings(
                latest_file=os.path.join(tmp, "latest.json"),
                report_file=os.path.join(tmp, "report.md"),
                universe_file=os.path.join(tmp, "universe.json"),
                positions_file=os.path.join(tmp, "pos.json"),
                cache_dir=os.path.join(tmp, "cache"),
            )
            report = scanner.ScanReport(
                strategy=config.STRATEGY_NAME,
                as_of="2026-08-18",
                generated_at="2026-08-18T12:00:00Z",
                universe_count=1,
                elite_count=1,
                dynamic_count=0,
                scanned=1,
                skipped=0,
            )
            scanner.persist_report(report, settings, positions={})
            self.assertTrue(os.path.exists(settings.latest_file))
            self.assertTrue(os.path.exists(settings.report_file))


class TestFloorsheet(unittest.TestCase):
    def test_aggregate_floorsheet_rows(self):
        from floorsheet import aggregate_floorsheet_rows

        rows = [
            {
                "stockSymbol": "HDL",
                "contractQuantity": 100,
                "contractAmount": 118000.0,
                "businessDate": "2026-08-18",
            },
            {
                "stockSymbol": "HDL",
                "contractQuantity": 50,
                "contractAmount": 59000.0,
                "businessDate": "2026-08-18",
            },
            {
                "stockSymbol": "SHEL",
                "contractQuantity": 200,
                "contractAmount": 59600.0,
                "businessDate": "2026-08-18",
            },
        ]
        session = aggregate_floorsheet_rows(rows)
        self.assertEqual(session.business_date, "2026-08-18")
        self.assertEqual(session.total_rows, 3)
        self.assertEqual(session.symbol_count, 2)
        hdl = session.get("HDL")
        self.assertIsNotNone(hdl)
        assert hdl is not None
        self.assertEqual(hdl.quantity, 150)
        self.assertEqual(hdl.trades, 2)

    def test_apply_floorsheet_volume_patches_latest_bar(self):
        frame = ohlcv_from_close(np.linspace(100, 120, 70), volume=1000)
        from floorsheet import SymbolFloorsheet

        fs = SymbolFloorsheet(
            symbol="HDL", quantity=25000, turnover=2_950_000, trades=40, vwap=118.0
        )
        last_date = frame["businessDate"].iloc[-1].strftime("%Y-%m-%d")
        patched = scanner.apply_floorsheet_volume(frame, fs, last_date)
        self.assertEqual(float(patched["volume"].iloc[-1]), 25000.0)


class TestNepseApi(unittest.TestCase):
    def test_nepse_history_to_ohlcv(self):
        from nepse_api_client import nepse_history_to_ohlcv

        rows = [
            {
                "businessDate": "2026-08-17",
                "highPrice": 1185.0,
                "lowPrice": 1175.0,
                "closePrice": 1179.0,
                "totalTradedQuantity": 23412,
            },
            {
                "businessDate": "2026-08-18",
                "highPrice": 1184.6,
                "lowPrice": 1179.0,
                "closePrice": 1180.9,
                "totalTradedQuantity": 22481,
            },
        ]
        frame = nepse_history_to_ohlcv(rows)
        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(float(frame["close"].iloc[-1]), 1180.9)
        self.assertIn("open", frame.columns)


class TestLiveScanner(unittest.TestCase):
    def test_parse_and_prefer_live_over_today(self):
        import live_scanner as ls

        today = [{"symbol": "HDL", "closePrice": 1180.9, "openPrice": 1182, "highPrice": 1184.6, "lowPrice": 1179, "totalTradedQuantity": 100, "businessDate": "2026-08-19"}]
        live = [{"symbol": "HDL", "lastTradedPrice": 1190.0, "openPrice": 1182, "highPrice": 1191, "lowPrice": 1179, "totalTradeQuantity": 500, "businessDate": "2026-08-19"}]
        quotes = ls.merge_quotes(live, today)
        self.assertEqual(quotes["HDL"].close, 1190.0)
        self.assertEqual(quotes["HDL"].source, "live_market")
        self.assertEqual(quotes["HDL"].volume, 500)

    def test_overlay_replaces_same_day_and_appends_new_day(self):
        import live_scanner as ls

        frame = ohlcv_from_close(np.linspace(100, 110, 70), volume=1000)
        last = frame["businessDate"].iloc[-1].strftime("%Y-%m-%d")
        quote = ls.LiveQuote("HDL", last, 110, 112, 109, 111.5, 8000, source="live_market")
        same = ls.overlay_live_bar(frame, quote)
        self.assertEqual(len(same), len(frame))
        self.assertAlmostEqual(float(same["close"].iloc[-1]), 111.5)
        nxt = (pd.Timestamp(last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        q2 = ls.LiveQuote("HDL", nxt, 111.5, 115, 111, 114, 9000, source="live_market")
        appended = ls.overlay_live_bar(frame, q2)
        self.assertEqual(len(appended), len(frame) + 1)
        self.assertAlmostEqual(float(appended["close"].iloc[-1]), 114)

    def test_dedup_only_new_buy_sell(self):
        import live_scanner as ls

        buy = scanner.ScanRow(symbol="CIT", signal="BUY", date="2026-08-19", close=1000.0)
        hold = scanner.ScanRow(symbol="HDL", signal="HOLD", date="2026-08-19", close=1180.0)
        state: dict = {"sent": {}}
        first = ls.new_buy_sell_alerts([buy, hold], state)
        self.assertEqual([r.symbol for r in first], ["CIT"])
        second = ls.new_buy_sell_alerts([buy], state)
        self.assertEqual(second, [])
        sell = scanner.ScanRow(symbol="CIT", signal="SELL", date="2026-08-19", close=990.0)
        third = ls.new_buy_sell_alerts([sell], state)
        self.assertEqual([r.signal for r in third], ["SELL"])

    def test_run_live_once_sends_only_buy_sell(self):
        import live_scanner as ls

        sent: list[str] = []

        def fake_send(text, settings=None, token="", chat_id=""):
            sent.append(text)
            return True

        import notifier

        original = notifier.send_telegram
        notifier.send_telegram = fake_send
        ls.send_telegram = fake_send
        try:
            settings = config.Settings(
                live_state_file=os.path.join(tempfile.mkdtemp(), "live.json"),
                positions_file=os.path.join(tempfile.mkdtemp(), "pos.json"),
                cache_dir=tempfile.mkdtemp(),
            )
            crash = TestScannerSignals()._flip_buy_frame(40_000)
            # reuse buy frame as CIT history
            class FakeClient:
                def listed_scripts(self):
                    return [dc.ListedScript("CIT", "Citizen Investment Trust", "Investment")]

                def ohlcv_many(self, symbols):
                    return {"CIT": crash}

                def _nepse_client(self):
                    return self

                def market_snapshot(self):
                    last = crash["businessDate"].iloc[-1].strftime("%Y-%m-%d")
                    close = float(crash["close"].iloc[-1])
                    return (
                        {"isOpen": "OPEN", "asOf": last},
                        [{"symbol": "CIT", "lastTradedPrice": close, "openPrice": close, "highPrice": close, "lowPrice": close, "totalTradeQuantity": 40000, "businessDate": last}],
                        [],
                    )

            fresh = ls.run_live(
                settings=settings,
                client=FakeClient(),  # type: ignore[arg-type]
                once=True,
                send=True,
                snapshot_fn=FakeClient().market_snapshot,
            )
            self.assertTrue(any(r.signal == "BUY" for r in fresh))
            self.assertTrue(any("BUY" in t for t in sent))
        finally:
            notifier.send_telegram = original
            ls.send_telegram = original


class TestConfig(unittest.TestCase):
    def test_elite_basket_contains_required_names(self):
        basket = set(config.elite_basket())
        for symbol in ("HDL", "NLG", "CIT", "SHEL", "RADHI", "MFIL"):
            self.assertIn(symbol, basket)

    def test_default_telegram_chat_id(self):
        settings = config.load_settings()
        self.assertTrue(settings.telegram_chat_id)


if __name__ == "__main__":
    unittest.main()
