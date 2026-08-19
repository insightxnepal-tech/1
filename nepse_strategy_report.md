# NEPSE barbell strategy

Generated **2026-08-19**. Unofficial merolagani OHLCV. Not financial advice.

## What the data supports (and what it does not)

The old 4-rule candle scanner had a **27.5%** paper-trade win rate and did not beat NEPSE.

A stock-picking system with **>75% accuracy and market-beating returns after NEPSE costs was not found** on a 2023–2024 train / 2025–2026 test split (213 liquid ordinary equities). 20-session directional accuracy for “stock above 200 EMA” was **48% train / 37% test** — a coin flip, not 75%.

Two sleeves *are* justified:

1. **Core — NEPSE RSI cycle (80/40)** beat buy-and-hold over the full window by sitting in cash after extreme overbought prints.
2. **Satellite — 3% target / 12% stop bounce** printed **>75%** out-of-sample hit rate. That hit rate is mostly the 3-to-12 barrier ratio plus a bull filter. After **0.5%** round-trip costs it did **not** beat NEPSE as a standalone book. Cap it at **20%** of capital.

## Today's regime (2026-08-19)

- NEPSE **2622.48** · RSI **37.8** · 200 EMA **2694.19**
- **RISK-ON (RSI 37.8 ≤ 80 cycle; re-entry at ≤ 40)**

If RISK-ON: hold NEPSE (or an index-tracking fund) for ~80% of the book. If CASH: no new stock overlay either.

## Core: NEPSE RSI 80 / 40

Start invested. When daily RSI(14) closes **≥ 80**, go to cash (next session). When RSI closes **≤ 40**, buy NEPSE back. One position; no leverage.

### Train (through 2024)

- Window: **2023-02-01 → 2024-12-30**
- Strategy: **+16.21%** vs NEPSE buy-and-hold **+23.58%** (excess **-7.37 pts**)
- Time in market: **80.9%**
- Closed RSI cycles: **2**, win **100.0%**, avg **6.13%**

| Entry | Exit | P/L | Hold | Status |
| --- | --- | ---: | ---: | --- |
| 2023-02-01 | 2023-12-21 | +1.33% | 204d | closed |
| 2024-02-21 | 2024-07-15 | +10.94% | 93d | closed |
| 2024-09-24 | 2024-12-30 | +3.17% | 58d | open |

### Test (2025 onward)

- Window: **2025-01-01 → 2026-08-19**
- Strategy: **+18.12%** vs NEPSE buy-and-hold **+1.78%** (excess **+16.34 pts**)
- Time in market: **92.3%**
- Closed RSI cycles: **2**, win **100.0%**, avg **11.43%**

| Entry | Exit | P/L | Hold | Status |
| --- | --- | ---: | ---: | --- |
| 2025-01-01 | 2025-03-03 | +12.08% | 38d | closed |
| 2025-03-20 | 2025-07-23 | +10.77% | 82d | closed |
| 2025-08-18 | 2026-08-19 | -5.02% | 225d | open |

### Full sample

- Window: **2023-02-01 → 2026-08-19**
- Strategy: **+35.53%** vs NEPSE buy-and-hold **+24.19%** (excess **+11.34 pts**)
- Time in market: **86.1%**
- Closed RSI cycles: **4**, win **100.0%**, avg **9.3%**

| Entry | Exit | P/L | Hold | Status |
| --- | --- | ---: | ---: | --- |
| 2023-02-01 | 2023-12-21 | +1.33% | 204d | closed |
| 2024-02-21 | 2024-07-15 | +10.94% | 93d | closed |
| 2024-09-24 | 2025-03-03 | +14.17% | 97d | closed |
| 2025-03-20 | 2025-07-23 | +10.77% | 82d | closed |
| 2025-08-18 | 2026-08-19 | -5.02% | 225d | open |

Closed-cycle counts are small. The NAV edge vs buy-and-hold is the real test, not the 100% cycle hit rate.

## Satellite: high-hit-rate bounce (optional)

All of:

- NEPSE close > 200 EMA
- Stock close > 200 EMA and 20 EMA > 200 EMA
- 63-day return ahead of NEPSE
- RSI(14) < 42
- Volume > 20-day average

Exit: **+3%** target, **−12%** stop, or **30** sessions. Max **5** names. Size **4%** of the total book per name.

After 0.5% round-trip cost:

| Split | Trades | Win rate | Avg P/L | Avg hold |
| --- | ---: | ---: | ---: | ---: |
| Train ≤ 2024 | 68 | 86.8% | 0.99% | 7.7d |
| Test ≥ 2025 | 103 | 81.6% | 0.1% | 7.3d |

Use this sleeve for hit-rate, not for beating NEPSE. If train and test win rates both stay above 75% but average P/L after costs is ~0, the overlay is optional.

## How to run

```bash
python nepse_strategy.py --backtest
python nepse_strategy.py --scan
```

Not financial advice. Survivorship (currently listed names only), unofficial prices, and NEPSE commissions matter.
