#!/usr/bin/env python3
"""
Daily candle scanner — TradingView-style 200 EMA / 20 EMA bounce.

ENTRY (all four must be true on the latest daily candle):
  1. Price is ABOVE the orange 200 EMA
  2. RSI dipped into the 38–48 zone (this candle or last few days)
  3. GREEN candle bounced off or closed near the blue 20 EMA
  4. Daily volume is higher than the 20-day volume MA

EXIT (open positions only — any one triggers):
  1. Close below the 20 EMA (bounce support lost)
  2. Close below the 200 EMA (uptrend broken)
  3. RSI >= 70 (overbought take-profit)

By default scans every ordinary NEPSE equity listed on merolagani.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

import pandas as pd
import requests

# ── Strategy constants (match the manual candle loop) ─────────────
EMA_TREND = 200
EMA_BOUNCE = 20
VOL_MA = 20
RSI_LEN = 14
RSI_ZONE = (38.0, 48.0)
RSI_LOOKBACK = 3  # allow the RSI dip on this candle or the prior 2
RSI_DIP_MAX = 55.0  # still counts if RSI is just lifting out of the zone
RSI_OVERBOUGHT = 70.0
NEAR_PCT = 0.015  # 1.5% of price
NEAR_ATR_MULT = 0.5  # or 0.5 × ATR, whichever is larger
MIN_HISTORY = 200
HISTORY_CALENDAR_DAYS = 1100
MAX_WORKERS = 8
REQUEST_TIMEOUT = 25
RETRY_COUNT = 3

POSITIONS_FILE = os.getenv("CANDLE_POSITIONS_FILE", "candle_positions.json")
LATEST_FILE = os.getenv("CANDLE_LATEST_FILE", "candle_scan_latest.json")
REPORT_FILE = os.getenv("CANDLE_REPORT_FILE", "candle_scan_report.md")
UNIVERSE_FILE = os.getenv("CANDLE_UNIVERSE_FILE", "candle_universe.json")
PORTFOLIO_FILE = os.getenv("PORTFOLIO_FILE", "portfolio_data.json")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
# Default is the InsightX Nepal alert chat used by NEPAPI. Override with env.
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8563709547")

MEROLAGANI_ORIGIN = "https://merolagani.com"
COMPANY_LIST_URL = f"{MEROLAGANI_ORIGIN}/CompanyList.aspx"
CHART_URL = f"{MEROLAGANI_ORIGIN}/handlers/TechnicalChartHandler.ashx"
SKIP_NAME_FRAGMENTS = (
    "Mutual Fund",
    "Debenture",
    "Bond",
    "Promoter",
    "Preference",
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── Data classes ──────────────────────────────────────────────────
@dataclass
class ListedScript:
    symbol: str
    name: str
    sector: str = ""


@dataclass
class CandleSignal:
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: float
    ema200: float
    rsi: float
    vol_ma20: float
    atr: float
    above_200: bool
    rsi_dip: bool
    green_near_20: bool
    volume_ok: bool
    entry: bool
    exit_reasons: list = field(default_factory=list)
    name: str = ""
    sector: str = ""
    bars: int = 0

    @property
    def signal(self) -> str:
        if self.entry:
            return "ENTRY"
        if self.exit_reasons:
            return "EXIT"
        return "NONE"

    @property
    def passed_count(self) -> int:
        return int(self.above_200) + int(self.rsi_dip) + int(self.green_near_20) + int(self.volume_ok)


# ── Indicators ────────────────────────────────────────────────────
def _rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder moving average (TradingView RMA / RSI smoothing)."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ema20, ema200, rsi, vol_ma20, atr, open to a daily OHLCV frame.

    Expected columns: businessDate, high, low, close, volume.
    Optional: open. If missing, previous close is used as open.
    """
    out = df.copy().sort_values("businessDate").reset_index(drop=True)
    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)

    if "open" not in out.columns:
        out["open"] = close.shift(1).fillna(close)
    else:
        out["open"] = out["open"].astype(float).fillna(close.shift(1)).fillna(close)

    out["ema20"] = close.ewm(span=EMA_BOUNCE, adjust=False).mean()
    out["ema200"] = close.ewm(span=EMA_TREND, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    rs = _rma(gain, RSI_LEN) / _rma(loss, RSI_LEN).replace(0, 1e-10)
    out["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.rolling(RSI_LEN).mean()
    out["vol_ma20"] = volume.rolling(VOL_MA).mean()
    return out


def _near_distance(price: float, atr: float) -> float:
    atr_part = (atr if pd.notna(atr) and atr > 0 else 0.0) * NEAR_ATR_MULT
    return max(price * NEAR_PCT, atr_part, price * 0.005)


def evaluate_latest(df: pd.DataFrame, symbol: str = "") -> Optional[CandleSignal]:
    """Apply the manual candle loop to the last row of an indicator frame."""
    if df is None or len(df) < MIN_HISTORY:
        return None
    if df["ema200"].iloc[-1] != df["ema200"].iloc[-1]:  # NaN
        return None

    last = df.iloc[-1]
    lookback = min(RSI_LOOKBACK, len(df))
    recent_rsi = df["rsi"].iloc[-lookback:]

    price = float(last["close"])
    open_px = float(last["open"])
    high = float(last["high"])
    low = float(last["low"])
    ema20 = float(last["ema20"])
    ema200 = float(last["ema200"])
    rsi = float(last["rsi"])
    vol = float(last["volume"])
    vol_ma = float(last["vol_ma20"]) if pd.notna(last["vol_ma20"]) else 0.0
    atr = float(last["atr"]) if pd.notna(last["atr"]) else 0.0

    above_200 = price > ema200

    in_zone = (recent_rsi >= RSI_ZONE[0]) & (recent_rsi <= RSI_ZONE[1])
    rsi_dip = bool(in_zone.any()) and rsi <= RSI_DIP_MAX

    green = price > open_px
    dist = _near_distance(price, atr)
    bounced = (low <= ema20 + dist) and (price >= ema20 - dist)
    closed_near = abs(price - ema20) <= dist
    green_near_20 = bool(green and (bounced or closed_near))

    volume_ok = vol_ma > 0 and vol > vol_ma

    entry = bool(above_200 and rsi_dip and green_near_20 and volume_ok)

    exit_reasons: list[str] = []
    if price < ema20:
        exit_reasons.append(f"Close below 20 EMA ({ema20:.2f})")
    if price < ema200:
        exit_reasons.append(f"Close below 200 EMA ({ema200:.2f})")
    if rsi >= RSI_OVERBOUGHT:
        exit_reasons.append(f"RSI overbought ({rsi:.1f} >= {RSI_OVERBOUGHT:.0f})")

    bdate = last["businessDate"]
    if hasattr(bdate, "strftime"):
        date_str = bdate.strftime("%Y-%m-%d")
    else:
        date_str = str(bdate)[:10]

    return CandleSignal(
        symbol=symbol,
        date=date_str,
        open=round(open_px, 2),
        high=round(high, 2),
        low=round(low, 2),
        close=round(price, 2),
        volume=round(vol, 0),
        ema20=round(ema20, 2),
        ema200=round(ema200, 2),
        rsi=round(rsi, 1),
        vol_ma20=round(vol_ma, 0),
        atr=round(atr, 2),
        above_200=above_200,
        rsi_dip=rsi_dip,
        green_near_20=green_near_20,
        volume_ok=volume_ok,
        entry=entry,
        exit_reasons=exit_reasons,
        bars=len(df),
    )


def apply_position_rules(
    signal: CandleSignal,
    open_positions: dict,
) -> str:
    """
    Decide what to notify.

    ENTRY only when the setup is new (not already in an open position).
    EXIT only for an existing open position (never on the same day as entry).
    """
    held = signal.symbol in open_positions
    if signal.entry and not held:
        return "ENTRY"
    if held and signal.exit_reasons and not signal.entry:
        return "EXIT"
    return "NONE"


def update_positions(
    positions: dict,
    signal: CandleSignal,
    action: str,
) -> dict:
    out = dict(positions)
    if action == "ENTRY":
        out[signal.symbol] = {
            "entry_date": signal.date,
            "entry_price": signal.close,
            "ema20": signal.ema20,
            "ema200": signal.ema200,
            "rsi": signal.rsi,
        }
    elif action == "EXIT" and signal.symbol in out:
        del out[signal.symbol]
    return out


# ── Persistence ───────────────────────────────────────────────────
def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not read {path}: {e}")
    return default


def save_json(path: str, payload) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def load_positions() -> dict:
    data = load_json(POSITIONS_FILE, {})
    return data if isinstance(data, dict) else {}


def load_portfolio_symbols() -> list[str]:
    data = load_json(PORTFOLIO_FILE, {})
    if isinstance(data, dict):
        return [str(s).upper() for s in data.keys()]
    return []


def load_latest_scan() -> dict:
    return load_json(LATEST_FILE, {})


# ── Universe (all NEPSE scripts) ──────────────────────────────────
_SYMBOL_ROW_RE = re.compile(
    r"CompanyDetail\.aspx\?symbol=([A-Z0-9]+)[^<]*</a>\s*</td>\s*"
    r'<td class="text-left">\s*([^<]+?)\s*</td>',
    re.IGNORECASE,
)
_SECTOR_RE = re.compile(
    r'href="#collapse_\d+"[^>]*>([^<]+)</a>(.*?)(?=href="#collapse_\d+"|\Z)',
    re.IGNORECASE | re.DOTALL,
)


def _is_ordinary_equity(symbol: str, name: str = "", sector: str = "") -> bool:
    text = f"{symbol} {name} {sector}"
    if any(s.lower() in text.lower() for s in SKIP_NAME_FRAGMENTS):
        return False
    if symbol.upper().endswith("PO"):
        return False
    return True


def parse_company_list_html(html: str) -> list[ListedScript]:
    """Parse merolagani CompanyList.aspx into listed scripts."""
    scripts: list[ListedScript] = []
    seen: set[str] = set()
    for sector, body in _SECTOR_RE.findall(html):
        sector_name = re.sub(r"\s+", " ", sector).strip()
        for symbol, name in _SYMBOL_ROW_RE.findall(body):
            symbol = symbol.strip().upper()
            name = re.sub(r"\s+", " ", name).strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            scripts.append(ListedScript(symbol=symbol, name=name, sector=sector_name))
    if not scripts:
        for symbol, name in _SYMBOL_ROW_RE.findall(html):
            symbol = symbol.strip().upper()
            name = re.sub(r"\s+", " ", name).strip()
            if symbol and symbol not in seen:
                seen.add(symbol)
                scripts.append(ListedScript(symbol=symbol, name=name))
    return scripts


_THREAD_LOCAL = threading.local()


def http_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/html, */*",
            }
        )
        _THREAD_LOCAL.session = session
    return session


def fetch_listed_scripts(session: Optional[requests.Session] = None) -> list[ListedScript]:
    sess = session or http_session()
    last_error = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            res = sess.get(COMPANY_LIST_URL, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            scripts = parse_company_list_html(res.text)
            if scripts:
                return scripts
            last_error = RuntimeError("CompanyList.aspx parsed 0 symbols")
        except Exception as e:
            last_error = e
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Could not load NEPSE company list: {last_error}")


def merolagani_chart_to_ohlcv(data: dict) -> pd.DataFrame:
    if not isinstance(data, dict):
        return pd.DataFrame()
    if str(data.get("s") or "").lower() == "no_data":
        return pd.DataFrame()
    needed = {"t", "o", "h", "l", "c", "v"}
    if not needed.issubset(data.keys()) or not data["t"]:
        return pd.DataFrame()
    timestamps = pd.to_datetime(data["t"], unit="s", utc=True)
    try:
        if isinstance(timestamps, pd.Series):
            business = timestamps.dt.tz_convert("Asia/Kathmandu").dt.tz_localize(None)
        else:
            business = timestamps.tz_convert("Asia/Kathmandu").tz_localize(None)
    except (TypeError, ValueError, OverflowError, AttributeError):
        business = timestamps.tz_localize(None) if getattr(timestamps, "tz", None) else timestamps
    if isinstance(business, pd.Series):
        business_dates = business.dt.normalize()
    else:
        business_dates = business.normalize()
    df = pd.DataFrame(
        {
            "businessDate": business_dates,
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"],
        }
    )
    return df.drop_duplicates("businessDate").sort_values("businessDate")


def history_to_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Convert NEPSE-style history rows (or already-renamed rows) to OHLCV."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    rename = {
        "closePrice": "close",
        "highPrice": "high",
        "lowPrice": "low",
        "openPrice": "open",
        "totalTradedQuantity": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "volume" not in df.columns and "totalTradedQuantity" in df.columns:
        df["volume"] = df["totalTradedQuantity"]
    needed = {"businessDate", "high", "low", "close", "volume"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"history missing columns: {missing}")
    df["businessDate"] = pd.to_datetime(df["businessDate"])
    df = df.drop_duplicates("businessDate").sort_values("businessDate")
    return df


def fetch_symbol_ohlcv(
    symbol: str,
    session: Optional[requests.Session] = None,
    calendar_days: int = HISTORY_CALENDAR_DAYS,
) -> pd.DataFrame:
    sess = session or http_session()
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=calendar_days)).timestamp())
    params = {
        "type": "get_advanced_chart",
        "symbol": symbol,
        "resolution": "1D",
        "rangeStartDate": start_ts,
        "rangeEndDate": end_ts,
        "isAdjust": "1",
        "currencyCode": "NPR",
    }
    headers = {
        "Referer": f"{MEROLAGANI_ORIGIN}/CompanyDetail.aspx?symbol={symbol}",
        "X-Requested-With": "XMLHttpRequest",
    }
    last_error = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            res = sess.get(
                CHART_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            res.raise_for_status()
            ctype = (res.headers.get("content-type") or "").lower()
            if "html" in ctype:
                last_error = RuntimeError("HTML instead of JSON")
                time.sleep(1.2 * attempt)
                continue
            return merolagani_chart_to_ohlcv(res.json())
        except Exception as e:
            last_error = e
            time.sleep(1.2 * attempt)
    print(f"  {symbol}: history error {last_error}")
    return pd.DataFrame()


def resolve_scripts(
    scan_all: bool,
    only: Optional[Iterable[str]],
    listed: Optional[list[ListedScript]] = None,
) -> list[ListedScript]:
    if only:
        wanted = [s.strip().upper() for s in only if s.strip()]
        by_symbol = {s.symbol: s for s in (listed or [])}
        return [
            by_symbol.get(sym, ListedScript(symbol=sym, name=sym))
            for sym in wanted
        ]
    if not listed:
        listed = []
    if scan_all:
        return [
            s for s in listed if _is_ordinary_equity(s.symbol, s.name, s.sector)
        ]
    portfolio = set(load_portfolio_symbols())
    return [s for s in listed if s.symbol in portfolio] or [
        ListedScript(symbol=sym, name=sym) for sym in portfolio
    ]


# ── Telegram / reports ────────────────────────────────────────────
def _missing_rules(s) -> list[str]:
    above_200 = s.above_200 if hasattr(s, "above_200") else s.get("above_200")
    rsi_dip = s.rsi_dip if hasattr(s, "rsi_dip") else s.get("rsi_dip")
    green_near_20 = s.green_near_20 if hasattr(s, "green_near_20") else s.get("green_near_20")
    volume_ok = s.volume_ok if hasattr(s, "volume_ok") else s.get("volume_ok")
    missing = []
    if not above_200:
        missing.append("below 200 EMA")
    if not rsi_dip:
        missing.append("RSI not 38–48")
    if not green_near_20:
        missing.append("no green 20 EMA bounce")
    if not volume_ok:
        missing.append("volume ≤ MA20")
    return missing


def format_telegram(
    entries: list[CandleSignal],
    exits: list[tuple[CandleSignal, dict]],
    scanned: int,
    as_of: str,
    skipped: int = 0,
    near_misses: Optional[list] = None,
) -> str:
    lines = [f"🕯️ *Daily Candle Scan — {as_of}*", ""]

    if entries:
        lines.append(f"🟢 *ENTRY FOUND ({len(entries)})*")
        lines.append("_Price > 200 EMA · RSI 38–48 · green 20 EMA bounce · vol > MA20_")
        lines.append("")
        for s in entries:
            vol_x = (s.volume / s.vol_ma20) if s.vol_ma20 else 0
            lines.append(f"• *{s.symbol}* @ Rs {s.close:.2f}")
            lines.append(
                f"  200 EMA {s.ema200:.2f} | 20 EMA {s.ema20:.2f} | RSI {s.rsi:.1f}"
            )
            lines.append(
                f"  Vol {vol_x:.1f}× MA20 | O {s.open:.2f} H {s.high:.2f} L {s.low:.2f}"
            )
            lines.append("")
    else:
        lines.append("🟢 *ENTRY FOUND:* none")
        lines.append("")

    if exits:
        lines.append(f"🛑 *EXIT FOUND ({len(exits)})*")
        lines.append("")
        for s, pos in exits:
            entry_px = pos.get("entry_price")
            entry_dt = pos.get("entry_date", "?")
            pnl = ""
            if isinstance(entry_px, (int, float)) and entry_px:
                pct = (s.close - entry_px) / entry_px * 100
                pnl = f" | P/L {pct:+.1f}%"
            lines.append(f"• *{s.symbol}* @ Rs {s.close:.2f}{pnl}")
            lines.append(f"  Entered Rs {entry_px} on {entry_dt}")
            lines.append(f"  Reason: {'; '.join(s.exit_reasons)}")
            lines.append("")
    else:
        lines.append("🛑 *EXIT FOUND:* none")
        lines.append("")

    if near_misses:
        lines.append(f"🟡 *NEAR MISS ({len(near_misses)} — 3 of 4 rules)*")
        lines.append("")
        for s in near_misses:
            if isinstance(s, dict):
                symbol = s.get("symbol", "")
                close = float(s.get("close") or 0)
                rsi = float(s.get("rsi") or 0)
            else:
                symbol = s.symbol
                close = s.close
                rsi = s.rsi
            missing = _missing_rules(s)
            lines.append(f"• *{symbol}* @ Rs {close:.2f} | RSI {rsi:.1f}")
            lines.append(f"  Missing: {', '.join(missing)}")
            lines.append("")

    lines.append(f"_Scanned {scanned} stocks ({skipped} skipped, need {MIN_HISTORY}+ days)._")
    lines.append("_Not financial advice._")
    return "\n".join(lines).strip() + "\n"


def format_markdown_report(
    entries: list[CandleSignal],
    exits: list[tuple[CandleSignal, dict]],
    signals: list[CandleSignal],
    scanned: int,
    skipped: int,
    as_of: str,
    universe_count: int,
    skipped_non_equity: int,
) -> str:
    near = [s for s in signals if not s.entry and s.passed_count == 3]
    near.sort(key=lambda s: s.symbol)
    entries_sorted = sorted(entries, key=lambda s: s.symbol)
    lines = [
        f"# NEPSE daily candle scan — {as_of}",
        "",
        "Setup: close > 200 EMA, RSI 38–48 dip, green 20 EMA bounce, volume > MA20.",
        "",
        f"- Listed ordinary equities in universe: **{universe_count}**",
        f"- Non-equity scripts skipped (MF / debenture / bond / promoter / preference): **{skipped_non_equity}**",
        f"- Scripts with enough history to score: **{scanned}**",
        f"- Skipped (thin history / no data): **{skipped}**",
        f"- ENTRY: **{len(entries_sorted)}**",
        f"- EXIT (open positions only): **{len(exits)}**",
        f"- Near-miss (3 of 4 rules): **{len(near)}**",
        "",
        "## ENTRY",
        "",
    ]
    if entries_sorted:
        lines.append("| Symbol | Name | Sector | Close | 20 EMA | 200 EMA | RSI | Vol / MA20 |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for s in entries_sorted:
            vol_x = (s.volume / s.vol_ma20) if s.vol_ma20 else 0
            lines.append(
                f"| {s.symbol} | {s.name or s.symbol} | {s.sector} | "
                f"{s.close:.2f} | {s.ema20:.2f} | {s.ema200:.2f} | {s.rsi:.1f} | {vol_x:.2f}× |"
            )
    else:
        lines.append("None.")
    lines += ["", "## EXIT", ""]
    if exits:
        lines.append("| Symbol | Close | Reason |")
        lines.append("| --- | ---: | --- |")
        for s, pos in exits:
            lines.append(
                f"| {s.symbol} | {s.close:.2f} | {'; '.join(s.exit_reasons)} "
                f"(entered {pos.get('entry_price')} on {pos.get('entry_date', '?')}) |"
            )
    else:
        lines.append("None (no open paper positions, or none met an exit rule).")
    lines += ["", "## Near misses (3 of 4)", ""]
    if near:
        lines.append("| Symbol | Name | Close | RSI | Missing |")
        lines.append("| --- | --- | ---: | ---: | --- |")
        for s in near:
            missing = []
            if not s.above_200:
                missing.append("below 200 EMA")
            if not s.rsi_dip:
                missing.append("RSI not 38–48")
            if not s.green_near_20:
                missing.append("no green 20 EMA bounce")
            if not s.volume_ok:
                missing.append("volume ≤ MA20")
            lines.append(
                f"| {s.symbol} | {s.name or s.symbol} | {s.close:.2f} | {s.rsi:.1f} | "
                f"{', '.join(missing)} |"
            )
    else:
        lines.append("None.")
    lines += ["", "_Not financial advice. Unofficial merolagani OHLCV._", ""]
    return "\n".join(lines)


def send_telegram(text: str, token: str = "", chat_id: str = "") -> bool:
    token = token or TELEGRAM_TOKEN
    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not token:
        print("Telegram skipped: TELEGRAM_TOKEN not set. Chat id is ready; add a live BotFather token to send.")
        return False
    if not chat_id:
        print("Telegram skipped: TELEGRAM_CHAT_ID not set.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        try:
            res = requests.post(
                url,
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
                timeout=20,
            )
            print(f"Telegram status {res.status_code}: {res.text[:200]}")
            if res.status_code != 200:
                # Underscores in names can break legacy Markdown; retry plain.
                res = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=20,
                )
                print(f"Telegram plain status {res.status_code}: {res.text[:200]}")
                if res.status_code != 200:
                    ok = False
        except Exception as e:
            print(f"Telegram send error: {e}")
            ok = False
    return ok


def send_telegram_document(
    path: str,
    caption: str = "",
    token: str = "",
    chat_id: str = "",
) -> bool:
    token = token or TELEGRAM_TOKEN
    chat_id = chat_id or TELEGRAM_CHAT_ID
    if not token or not chat_id or not os.path.exists(path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(path, "rb") as f:
            res = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": (os.path.basename(path), f, "text/markdown")},
                timeout=30,
            )
        print(f"Telegram document status {res.status_code}: {res.text[:200]}")
        return res.status_code == 200
    except Exception as e:
        print(f"Telegram document error: {e}")
        return False


def telegram_text_from_payload(payload: dict) -> str:
    msg = payload.get("message") or ""
    near = payload.get("near_misses") or []
    if not near:
        return msg
    # Rebuild so the chat gets entries + near misses, not just the short summary.
    entries = []
    for raw in payload.get("entries") or []:
        entries.append(CandleSignal(**{k: v for k, v in raw.items() if k in CandleSignal.__dataclass_fields__}))
    exits = []
    for item in payload.get("exits") or []:
        raw = item.get("signal") or item
        sig = CandleSignal(**{k: v for k, v in raw.items() if k in CandleSignal.__dataclass_fields__})
        exits.append((sig, item.get("position") or {}))
    return format_telegram(
        entries,
        exits,
        scanned=payload.get("scanned") or 0,
        as_of=payload.get("as_of") or "?",
        skipped=payload.get("skipped") or 0,
        near_misses=near,
    )


def send_latest_report() -> bool:
    payload = load_latest_scan()
    if not payload:
        print(f"No scan to send: {LATEST_FILE} missing or empty.")
        return False
    text = telegram_text_from_payload(payload)
    ok = send_telegram(text)
    caption = f"NEPSE daily candle scan — {payload.get('as_of', '')}"
    ok_doc = send_telegram_document(REPORT_FILE, caption=caption)
    if not ok:
        print("Telegram message delivery failed.")
    if not ok_doc:
        print("Telegram document delivery failed (message may still have been sent).")
    return ok


# ── Scan driver ───────────────────────────────────────────────────
def scan_ohlcv_map(
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    positions: dict,
) -> tuple[list[CandleSignal], list[tuple[CandleSignal, dict]], dict, int]:
    entries: list[CandleSignal] = []
    exits: list[tuple[CandleSignal, dict]] = []
    new_positions = dict(positions)
    skipped = 0

    for symbol, raw in ohlcv_by_symbol.items():
        if raw is None or len(raw) < MIN_HISTORY:
            skipped += 1
            continue
        try:
            needed = {"ema20", "ema200", "rsi", "vol_ma20"}
            indicated = raw if needed.issubset(raw.columns) else compute_indicators(raw)
            signal = evaluate_latest(indicated, symbol=symbol)
        except Exception as e:
            print(f"  {symbol}: evaluate error {e}")
            skipped += 1
            continue
        if signal is None:
            skipped += 1
            continue

        action = apply_position_rules(signal, new_positions)
        if action == "ENTRY":
            entries.append(signal)
            new_positions = update_positions(new_positions, signal, action)
            print(f"  🟢 ENTRY {symbol} @ {signal.close} RSI {signal.rsi}")
        elif action == "EXIT":
            pos = dict(new_positions.get(symbol, {}))
            exits.append((signal, pos))
            new_positions = update_positions(new_positions, signal, action)
            print(f"  🛑 EXIT  {symbol} @ {signal.close} {signal.exit_reasons}")
        else:
            flags = []
            if not signal.above_200:
                flags.append("below200")
            if not signal.rsi_dip:
                flags.append("rsi")
            if not signal.green_near_20:
                flags.append("ema20")
            if not signal.volume_ok:
                flags.append("vol")
            print(f"  · {symbol} skip ({', '.join(flags) or 'held'})")

    return entries, exits, new_positions, skipped


def _fetch_one(symbol: str) -> tuple[str, pd.DataFrame]:
    return symbol, fetch_symbol_ohlcv(symbol)


def collect_ohlcv(symbols: list[str], workers: int = MAX_WORKERS) -> dict[str, pd.DataFrame]:
    ohlcv_by_symbol: dict[str, pd.DataFrame] = {}
    total = len(symbols)
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_fetch_one, symbol): symbol for symbol in symbols}
        for fut in as_completed(futures):
            symbol = futures[fut]
            done += 1
            try:
                _, df = fut.result()
            except Exception as e:
                print(f"  {symbol}: history error {e}")
                continue
            if df is not None and not df.empty:
                ohlcv_by_symbol[symbol] = df
            if done % 25 == 0 or done == total:
                print(f"    Progress: {done}/{total} ({len(ohlcv_by_symbol)} with data)")
    return ohlcv_by_symbol


def evaluate_all_signals(
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    meta: dict[str, ListedScript],
) -> list[CandleSignal]:
    signals: list[CandleSignal] = []
    for symbol, raw in ohlcv_by_symbol.items():
        if raw is None or len(raw) < MIN_HISTORY:
            continue
        needed = {"ema20", "ema200", "rsi", "vol_ma20"}
        indicated = raw if needed.issubset(raw.columns) else compute_indicators(raw)
        signal = evaluate_latest(indicated, symbol=symbol)
        if signal is None:
            continue
        info = meta.get(symbol)
        if info:
            signal.name = info.name
            signal.sector = info.sector
        signals.append(signal)
    return signals


def run_scan(
    scan_all: bool = True,
    symbols: Optional[list[str]] = None,
    send: bool = True,
    persist: bool = True,
    workers: int = MAX_WORKERS,
    fresh: bool = False,
) -> dict:
    session = http_session()
    listed = fetch_listed_scripts(session)
    skipped_non_equity = sum(
        1 for s in listed if not _is_ordinary_equity(s.symbol, s.name, s.sector)
    )
    universe = resolve_scripts(scan_all=scan_all, only=symbols, listed=listed)
    meta = {s.symbol: s for s in listed}
    positions = {} if fresh or os.getenv("CANDLE_FRESH", "") == "1" else load_positions()
    for held in positions:
        if held not in meta:
            universe.append(ListedScript(symbol=held, name=held))
        elif all(s.symbol != held for s in universe):
            universe.append(meta[held])

    print(
        f"🕯️ Candle scan: {len(universe)} ordinary scripts "
        f"({len(listed)} listed, {skipped_non_equity} non-equity skipped), "
        f"{len(positions)} open positions"
    )

    ohlcv_by_symbol = collect_ohlcv([s.symbol for s in universe], workers=workers)
    entries, exits, new_positions, skipped = scan_ohlcv_map(ohlcv_by_symbol, positions)
    all_signals = evaluate_all_signals(ohlcv_by_symbol, meta)
    sig_map = {s.symbol: s for s in all_signals}
    for s in entries:
        info = sig_map.get(s.symbol)
        if info:
            s.name, s.sector, s.bars = info.name, info.sector, info.bars
    for s, _ in exits:
        info = sig_map.get(s.symbol)
        if info:
            s.name, s.sector, s.bars = info.name, info.sector, info.bars

    as_of = date.today().isoformat()
    if entries:
        as_of = entries[0].date
    elif exits:
        as_of = exits[0][0].date
    elif all_signals:
        as_of = all_signals[0].date

    near_misses = [s for s in all_signals if not s.entry and s.passed_count == 3]
    # Telegram/report list every script that matches today, even if already held.
    setups = sorted([s for s in all_signals if s.entry], key=lambda s: s.symbol)
    msg = format_telegram(
        setups,
        exits,
        scanned=len(ohlcv_by_symbol),
        as_of=as_of,
        skipped=skipped,
        near_misses=near_misses,
    )
    report = format_markdown_report(
        setups,
        exits,
        all_signals,
        scanned=len(ohlcv_by_symbol) - skipped,
        skipped=skipped + (len(universe) - len(ohlcv_by_symbol)),
        as_of=as_of,
        universe_count=len(universe),
        skipped_non_equity=skipped_non_equity,
    )
    print("\n" + msg)
    print(report)

    payload = {
        "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "listed": len(listed),
        "universe": len(universe),
        "skipped_non_equity": skipped_non_equity,
        "scanned": len(ohlcv_by_symbol) - skipped,
        "skipped": skipped + (len(universe) - len(ohlcv_by_symbol)),
        "entries": [asdict(s) for s in setups],
        "new_paper_entries": [asdict(s) for s in entries],
        "exits": [{"signal": asdict(s), "position": pos} for s, pos in exits],
        "near_misses": [asdict(s) for s in all_signals if not s.entry and s.passed_count == 3],
        "signals": [asdict(s) for s in sorted(all_signals, key=lambda x: x.symbol)],
        "open_positions": new_positions,
        "message": msg,
        "report": report,
    }

    telegram_ok = True
    if persist:
        save_json(POSITIONS_FILE, new_positions)
        save_json(LATEST_FILE, {k: v for k, v in payload.items() if k != "report"})
        save_json(
            UNIVERSE_FILE,
            [asdict(s) for s in universe],
        )
        with open(REPORT_FILE, "w") as f:
            f.write(report)
        print(f"Saved {POSITIONS_FILE}, {LATEST_FILE}, {UNIVERSE_FILE}, {REPORT_FILE}")

    if send:
        telegram_ok = send_telegram(msg)
        caption = f"NEPSE daily candle scan — {as_of}"
        send_telegram_document(REPORT_FILE, caption=caption)
    payload["telegram_ok"] = telegram_ok

    return payload


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Daily 200/20 EMA candle scanner for all NEPSE scripts")
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Scan all ordinary NEPSE equities (default)",
    )
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help="Scan portfolio_data.json only instead of the full market",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="Comma-separated symbols to scan (overrides --all / portfolio)",
    )
    parser.add_argument(
        "--send-latest",
        action="store_true",
        help="Send the saved candle_scan_latest.json report to Telegram and exit",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore candle_positions.json so today's matching setups are treated as new entries",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Do not send Telegram (print only)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not write position / latest JSON files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help="Parallel merolagani fetches",
    )
    args = parser.parse_args(argv)

    if args.send_latest:
        return 0 if send_latest_report() else 1

    only = [s for s in args.symbols.split(",") if s.strip()] or None
    payload = run_scan(
        scan_all=not args.portfolio,
        symbols=only,
        send=not args.no_telegram,
        persist=not args.no_persist,
        workers=args.workers,
        fresh=args.fresh,
    )
    if not args.no_telegram and not payload.get("telegram_ok", False):
        print("Telegram delivery failed.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
