# NEPSE Supertrend Elite Momentum Basket

Daily scanner and Telegram notifier for the **Supertrend Elite Momentum Basket** on the Nepal Stock Exchange.

Not financial advice. OHLCV and floorsheet come from the unofficial NEPSE API wrapper and can be delayed or incomplete.

## Strategy

| Rule | Definition |
| --- | --- |
| Indicator | Supertrend(period **10**, multiplier **3.0**) on Wilder **ATR-10** |
| **BUY** | Supertrend flips Green (bearish → bullish: close > Supertrend) **and** volume filter |
| Volume filter | 20-day volume SMA > 50-day volume SMA **or** RVOL > **1.2×** |
| **SELL / FULL EXIT** | Supertrend flips Red (close below the green Supertrend line) |
| Trailing stop | Current green Supertrend value |
| **HOLD** | Already in an established Supertrend bullish phase; report distance to the trail |

Elite Trend Compliance basket (always scanned):

`HDL, NLG, CIT, SHEL, FMDBL, SIKLES, MAKAR, SMJC, BHDC, USHL, MMKJL, MSHL, ANLB, RADHI, MFIL`

Dynamic names are ordinary NEPSE equities whose 20-day average volume and turnover clear the floors in `config.py`. Mutual funds, debentures, bonds, promoter, and preference shares are skipped.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set TELEGRAM_TOKEN
```

## Run

```bash
# Elite basket + liquid dynamic tickers (NEPSE API + floorsheet), Telegram if token set
python main.py

# Elite basket only (faster)
python main.py --elite-only

# Live tape: Telegram immediately on new BUY or SELL (forming candle)
python main.py --live
python main.py --live --once

# Merolagani fallback
python main.py --data-source merolagani --no-telegram
```

Outputs:

- `supertrend_scan_latest.json` — full payload
- `supertrend_scan_report.md` — human-readable summary
- `supertrend_positions.json` — paper BUY/SELL book with trailing stops
- `data/ohlcv/` — CSV OHLCV cache (gitignored)
- `data/floorsheet_latest.json` — latest NEPSE floorsheet aggregate (gitignored)

## Telegram

Set `TELEGRAM_TOKEN` (BotFather) and optionally `TELEGRAM_CHAT_ID` (defaults to `8563709547`).

- EOD Action `NEPSE Supertrend Elite scan → Telegram` after close (Sun–Thu ~4:45 PM NST)
- Live Action `NEPSE Supertrend LIVE BUY/SELL → Telegram` starts ~10:55 AM NST and polls until close

`--live` overlays NEPSE `live_market` (during the session) or `today_price` onto Supertrend(10, 3.0) and sends Telegram **only** when a new BUY or SELL appears. HOLD is not messaged in live mode. Intraday flips can reverse before the official close.

## Tests

```bash
python -m pytest test_supertrend_scanner.py -q
```

## Layout

```text
.cursorrules
config.py          # Supertrend 10/3.0, elite basket, liquidity floors
nepse_api_client.py # NEPSE API sync wrapper (history + floorsheet)
floorsheet.py      # Floorsheet aggregation by symbol
data_client.py     # NEPSE / merolagani listed scrips + OHLCV + floorsheet cache
indicators.py      # Wilder ATR, volume SMA, RVOL
supertrend.py      # Supertrend bands, flips, trailing stop
scanner.py         # universe, BUY/SELL/HOLD evaluation
notifier.py        # Telegram + markdown
main.py            # CLI
.github/workflows/supertrend_daily.yml
```
