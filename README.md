# NEPSE daily candle scanner

Scans **all ordinary NEPSE equities** for a TradingView-style daily setup:

1. Close **above** the 200 EMA
2. RSI (14) dipped into **38–48** on this candle or the prior two
3. **Green** candle bounced off / closed near the 20 EMA
4. Volume **above** the 20-day volume average

Open positions (if any) are marked **EXIT** when close drops below the 20 EMA or 200 EMA, or RSI is ≥ 70.

Daily OHLCV is loaded from [merolagani](https://merolagani.com/) chart data (the official NEPSE site is not reachable from many cloud IPs). Mutual funds, debentures, bonds, promoter, and preference shares are skipped.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Scan every listed script

```bash
python candle_scanner.py --all --no-telegram
```

Outputs:

- `candle_scan_latest.json` — full payload (entries, exits, every evaluated script)
- `candle_scan_report.md` — human-readable summary
- `candle_universe.json` — listed ordinary equities used for the run
- `candle_positions.json` — open paper positions (empty until an ENTRY fires)

Optional Telegram: set `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`, then omit `--no-telegram`.

## Tests

```bash
python -m pytest test_candle_scanner.py -q
```

Not financial advice. Data is unofficial and can be delayed or incomplete.
