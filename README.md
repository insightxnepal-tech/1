# NEPSE Supertrend Elite Momentum Basket

Daily scanner and Telegram notifier for the **Supertrend Elite Momentum Basket** on the Nepal Stock Exchange.

Not financial advice. OHLCV is unofficial merolagani chart data and can be delayed or incomplete.

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
# Elite basket + liquid dynamic tickers, write reports, send Telegram if token is set
python main.py

# Elite basket only (faster)
python main.py --elite-only --no-telegram

# Specific symbols
python main.py --symbols HDL,NLG,CIT --no-telegram

# Resend the last saved report
python main.py --send-latest
```

Outputs:

- `supertrend_scan_latest.json` — full payload
- `supertrend_scan_report.md` — human-readable summary
- `supertrend_positions.json` — paper BUY/SELL book with trailing stops
- `data/ohlcv/` — CSV cache (gitignored)

## Telegram

Set `TELEGRAM_TOKEN` (BotFather) and optionally `TELEGRAM_CHAT_ID` (defaults to `8563709547`). GitHub Action `NEPSE Supertrend Elite scan → Telegram` runs after NEPSE close (Sun–Thu ~4:45 PM NST) when those secrets are present on the repo.

## Tests

```bash
python -m pytest test_supertrend_scanner.py -q
```

## Layout

```text
.cursorrules
config.py          # Supertrend 10/3.0, elite basket, liquidity floors
data_client.py     # merolagani listed scrips + daily OHLCV
indicators.py      # Wilder ATR, volume SMA, RVOL
supertrend.py      # Supertrend bands, flips, trailing stop
scanner.py         # universe, BUY/SELL/HOLD evaluation
notifier.py        # Telegram + markdown
main.py            # CLI
.github/workflows/supertrend_daily.yml
```
