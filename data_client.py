"""Merolagani OHLCV client with retries, thread-local sessions, and disk cache."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
import requests

from config import (
    CHART_URL,
    COMPANY_LIST_URL,
    HISTORY_CALENDAR_DAYS,
    MEROLAGANI_ORIGIN,
    REQUEST_TIMEOUT,
    RETRY_COUNT,
    SKIP_NAME_FRAGMENTS,
    USER_AGENT,
    Settings,
    load_settings,
)

logger = logging.getLogger(__name__)

_SYMBOL_ROW_RE = re.compile(
    r"CompanyDetail\.aspx\?symbol=([A-Z0-9]+)[^<]*</a>\s*</td>\s*"
    r'<td class="text-left">\s*([^<]+?)\s*</td>',
    re.IGNORECASE,
)
_SECTOR_RE = re.compile(
    r'href="#collapse_\d+"[^>]*>([^<]+)</a>(.*?)(?=href="#collapse_\d+"|\Z)',
    re.IGNORECASE | re.DOTALL,
)

_THREAD_LOCAL = threading.local()


@dataclass(frozen=True)
class ListedScript:
    symbol: str
    name: str
    sector: str = ""
    instrument_type: str = ""


def is_ordinary_equity(symbol: str, name: str = "", sector: str = "", instrument_type: str = "") -> bool:
    if instrument_type and instrument_type != "Equity":
        return False
    text = f"{symbol} {name} {sector}"
    if any(fragment.lower() in text.lower() for fragment in SKIP_NAME_FRAGMENTS):
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


def fetch_listed_scripts(
    session: Optional[requests.Session] = None,
) -> list[ListedScript]:
    sess = session or http_session()
    last_error: Exception | RuntimeError | None = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            res = sess.get(COMPANY_LIST_URL, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            scripts = parse_company_list_html(res.text)
            if scripts:
                return scripts
            last_error = RuntimeError("CompanyList.aspx parsed 0 symbols")
        except Exception as exc:  # noqa: BLE001 — retry then raise
            last_error = exc
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
        business = (
            timestamps.tz_localize(None)
            if getattr(timestamps, "tz", None)
            else timestamps
        )
    if isinstance(business, pd.Series):
        business_dates = business.dt.normalize()
    else:
        business_dates = business.normalize()
    frame = pd.DataFrame(
        {
            "businessDate": business_dates,
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"],
        }
    )
    return frame.drop_duplicates("businessDate").sort_values("businessDate")


def _cache_path(cache_dir: str, symbol: str) -> str:
    return os.path.join(cache_dir, f"{symbol.upper()}.csv")


def load_cached_ohlcv(cache_dir: str, symbol: str) -> pd.DataFrame:
    path = _cache_path(cache_dir, symbol)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, parse_dates=["businessDate"])
        return frame.drop_duplicates("businessDate").sort_values("businessDate")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache read failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def save_cached_ohlcv(cache_dir: str, symbol: str, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        return
    os.makedirs(cache_dir, exist_ok=True)
    frame.to_csv(_cache_path(cache_dir, symbol), index=False)


def fetch_symbol_ohlcv(
    symbol: str,
    session: Optional[requests.Session] = None,
    calendar_days: int = HISTORY_CALENDAR_DAYS,
) -> pd.DataFrame:
    sess = session or http_session()
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = int(
        (datetime.now(timezone.utc) - timedelta(days=calendar_days)).timestamp()
    )
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
    last_error: Exception | None = None
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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1.2 * attempt)
    logger.warning("%s: history error %s", symbol, last_error)
    return pd.DataFrame()


class DataClient:
    """Fetch listed scripts, daily OHLCV, and NEPSE floorsheet."""

    def __init__(self, settings: Optional[Settings] = None, use_cache: bool = True):
        self.settings = settings or load_settings()
        self.use_cache = use_cache
        self._nepse = None

    @property
    def source(self) -> str:
        return (self.settings.data_source or "nepse").lower()

    def _nepse_client(self):
        if self._nepse is None:
            from nepse_api_client import NepseApiClient

            self._nepse = NepseApiClient(
                history_size=500,
                floorsheet_page_size=500,
                max_concurrency=self.settings.workers,
            )
        return self._nepse

    def listed_scripts(self) -> list[ListedScript]:
        if self.source == "merolagani":
            return fetch_listed_scripts()
        return self._nepse_client().listed_scripts()

    def ohlcv(self, symbol: str, force_refresh: bool = False) -> pd.DataFrame:
        symbol = symbol.upper()
        if self.use_cache and not force_refresh:
            cached = load_cached_ohlcv(self.settings.cache_dir, symbol)
            if not cached.empty:
                last = pd.Timestamp(cached["businessDate"].iloc[-1]).date()
                today = datetime.now(ZoneInfo("Asia/Kathmandu")).date()
                if last >= today:
                    return cached
        if self.source == "merolagani":
            frame = fetch_symbol_ohlcv(
                symbol, calendar_days=self.settings.history_calendar_days
            )
        else:
            frame = self._nepse_client().ohlcv(symbol)
        if self.use_cache and not frame.empty:
            save_cached_ohlcv(self.settings.cache_dir, symbol, frame)
        return frame

    def ohlcv_many(self, symbols: list[str], force_refresh: bool = False) -> dict[str, pd.DataFrame]:
        symbols = [s.upper() for s in symbols]
        if self.source == "merolagani":
            from concurrent.futures import ThreadPoolExecutor, as_completed

            out: dict[str, pd.DataFrame] = {}
            workers = max(1, self.settings.workers)

            def _one(symbol: str) -> tuple[str, pd.DataFrame]:
                return symbol, self.ohlcv(symbol, force_refresh=force_refresh)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_one, symbol): symbol for symbol in symbols}
                for future in as_completed(futures):
                    symbol, frame = future.result()
                    out[symbol] = frame
            return out
        if self.use_cache and not force_refresh:
            out: dict[str, pd.DataFrame] = {}
            missing: list[str] = []
            today = datetime.now(ZoneInfo("Asia/Kathmandu")).date()
            for symbol in symbols:
                cached = load_cached_ohlcv(self.settings.cache_dir, symbol)
                if not cached.empty and pd.Timestamp(cached["businessDate"].iloc[-1]).date() >= today:
                    out[symbol] = cached
                else:
                    missing.append(symbol)
            if missing:
                fetched = self._nepse_client().ohlcv_many(missing)
                for symbol, frame in fetched.items():
                    if self.use_cache and not frame.empty:
                        save_cached_ohlcv(self.settings.cache_dir, symbol, frame)
                    out[symbol] = frame
            return out
        fetched = self._nepse_client().ohlcv_many(symbols)
        if self.use_cache:
            for symbol, frame in fetched.items():
                if not frame.empty:
                    save_cached_ohlcv(self.settings.cache_dir, symbol, frame)
        return fetched

    def floorsheet_session(self, force_refresh: bool = False):
        from floorsheet import FloorsheetSession

        path = self.settings.floorsheet_cache_file
        if self.use_cache and not force_refresh and os.path.exists(path):
            try:
                import json

                with open(path, encoding="utf-8") as handle:
                    payload = json.load(handle)
                session = FloorsheetSession.from_dict(payload)
                if session.business_date:
                    return session
            except Exception as exc:  # noqa: BLE001
                logger.warning("Floorsheet cache read failed: %s", exc)
        if self.source == "merolagani":
            return FloorsheetSession()
        session = self._nepse_client().floorsheet_session()
        if self.use_cache and session.business_date:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            import json

            with open(path, "w", encoding="utf-8") as handle:
                json.dump(session.to_dict(), handle, indent=2)
                handle.write("\n")
        return session

    @staticmethod
    def scripts_as_dicts(scripts: list[ListedScript]) -> list[dict]:
        return [asdict(s) for s in scripts]
