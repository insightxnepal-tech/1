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

Optional Telegram: set `TELEGRAM_TOKEN` (BotFather) and optionally `TELEGRAM_CHAT_ID` (defaults to `8563709547`), then omit `--no-telegram`. To resend the last saved report without scanning again:

```bash
export TELEGRAM_TOKEN='<bot token>'
python candle_scanner.py --send-latest
```

The report lists **every ordinary NEPSE script that matches today**, plus exits and near-misses (3 of 4 rules). GitHub Action `NEPSE candle scan → Telegram` can run the same job after market close if those secrets are set on this repo.

## Monthly buy / sell accuracy

Replay the same ENTRY / EXIT rules on historical daily bars and print a table per calendar month:

```bash
python candle_accuracy.py
```

Outputs:

- `candle_accuracy_monthly.md` — monthly buy accuracy (1/5/10/20-session win rate) and sell accuracy (green-trade win rate)
- `candle_accuracy_monthly.json` — machine-readable payload
- `candle_accuracy_trades.csv` — every paper trade

OHLCV is cached under `data/ohlcv/` (gitignored). Pass `--no-cache` to refetch.

## Barbell strategy (index cycle + optional bounce)

The 4-rule candle book did not hit 75% accuracy or beat NEPSE. `nepse_strategy.py` is a two-sleeve playbook from a 2023–2024 train / 2025–2026 test split:

```bash
python nepse_strategy.py --backtest
python nepse_strategy.py --scan
```

- **Core:** hold NEPSE in an RSI(14) 80/40 cycle (cash after RSI ≥ 80, re-enter at ≤ 40). Full-sample NAV beat buy-and-hold; the bull-market train window lagged.
- **Satellite (optional, 20% cap):** 3% target / 12% stop bounce with >75% out-of-sample hit rate after 0.5% costs. It did **not** beat NEPSE as a standalone book.

Write-up: `nepse_strategy_report.md`. Not financial advice.

## Tests

```bash
python -m pytest test_candle_scanner.py test_candle_accuracy.py test_nepse_strategy.py -q
```

Not financial advice. Data is unofficial and can be delayed or incomplete.
