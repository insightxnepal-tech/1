"""Scan the Elite Trend Compliance basket and liquid NEPSE names."""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from config import (
    MIN_HISTORY_BARS,
    STRATEGY_NAME,
    Settings,
    elite_basket,
    load_settings,
)
from data_client import DataClient, ListedScript, is_ordinary_equity
from floorsheet import FloorsheetSession, SymbolFloorsheet
from indicators import volume_filter_ok
from supertrend import enrich_ohlcv

logger = logging.getLogger(__name__)
KATHMANDU = ZoneInfo("Asia/Kathmandu")


def _finite(value: object, default: float = float("nan")) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _round(value: float, digits: int = 2) -> float | None:
    number = _finite(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


@dataclass
class ScanRow:
    symbol: str
    name: str = ""
    sector: str = ""
    elite: bool = False
    date: str = ""
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    supertrend: float | None = None
    atr: float | None = None
    trend: int | None = None
    signal: str = "NONE"
    volume_ok: bool = False
    flip_buy: bool = False
    flip_sell: bool = False
    rvol: float | None = None
    vol_sma20: float | None = None
    vol_sma50: float | None = None
    turnover_sma20: float | None = None
    trailing_stop: float | None = None
    dist_to_trail_pct: float | None = None
    fs_quantity: float | None = None
    fs_turnover: float | None = None
    fs_trades: int | None = None
    bars: int = 0
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanReport:
    strategy: str
    as_of: str
    generated_at: str
    universe_count: int
    elite_count: int
    dynamic_count: int
    scanned: int
    skipped: int
    buys: list[ScanRow] = field(default_factory=list)
    sells: list[ScanRow] = field(default_factory=list)
    holds: list[ScanRow] = field(default_factory=list)
    blocked_buys: list[ScanRow] = field(default_factory=list)
    skipped_symbols: list[str] = field(default_factory=list)
    data_source: str = "nepse"
    floorsheet_date: str = ""
    floorsheet_rows: int = 0
    floorsheet_turnover: float = 0.0
    message: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        return payload


def nepal_today() -> str:
    return datetime.now(KATHMANDU).date().isoformat()


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
        handle.write("\n")


def load_positions(path: str) -> dict:
    data = load_json(path, {})
    return data if isinstance(data, dict) else {}


def _bar_date(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def apply_floorsheet_volume(
    frame: pd.DataFrame,
    fs_row: SymbolFloorsheet | None,
    business_date: str,
) -> pd.DataFrame:
    """Replace the latest bar volume with NEPSE floorsheet aggregate when dates match."""
    if frame is None or frame.empty or fs_row is None or not business_date:
        return frame
    out = frame.copy()
    last_idx = out.index[-1]
    last_date = _bar_date(out.loc[last_idx, "businessDate"])
    if last_date != business_date[:10]:
        return out
    out.loc[last_idx, "volume"] = float(fs_row.quantity)
    return out


def attach_floorsheet(row: ScanRow, fs_row: SymbolFloorsheet | None) -> None:
    if fs_row is None:
        return
    row.fs_quantity = round(fs_row.quantity, 0)
    row.fs_turnover = round(fs_row.turnover, 2)
    row.fs_trades = int(fs_row.trades)


def evaluate_symbol(
    symbol: str,
    frame: pd.DataFrame,
    *,
    name: str = "",
    sector: str = "",
    elite: bool = False,
    settings: Optional[Settings] = None,
) -> ScanRow:
    settings = settings or load_settings()
    row = ScanRow(symbol=symbol, name=name or symbol, sector=sector, elite=elite)
    if frame is None or frame.empty:
        row.note = "no OHLCV"
        return row
    row.bars = int(len(frame))
    if len(frame) < MIN_HISTORY_BARS:
        row.note = f"thin history ({len(frame)} bars)"
        return row

    indicated = enrich_ohlcv(
        frame,
        period=settings.supertrend_period,
        multiplier=settings.supertrend_multiplier,
    )
    last = indicated.iloc[-1]
    if not math.isfinite(_finite(last.get("supertrend"))):
        row.note = "supertrend not ready"
        return row

    close = _finite(last["close"])
    st = _finite(last["supertrend"])
    trend = int(last["trend"]) if math.isfinite(_finite(last.get("trend"))) else 0
    flip_buy = bool(last["flip_buy"])
    flip_sell = bool(last["flip_sell"])
    vol_sma20 = _finite(last.get("vol_sma20"))
    vol_sma50 = _finite(last.get("vol_sma50"))
    rvol = _finite(last.get("rvol"))
    volume_ok = volume_filter_ok(vol_sma20, vol_sma50, rvol, settings.rvol_threshold)

    if flip_buy and volume_ok:
        signal = "BUY"
    elif flip_buy and not volume_ok:
        signal = "BLOCKED_BUY"
        row.note = "green flip, volume filter failed"
    elif flip_sell:
        signal = "SELL"
    elif trend == 1:
        signal = "HOLD"
    else:
        signal = "NONE"

    trail = st if trend == 1 else float("nan")
    dist = ((close - st) / close * 100.0) if close and trend == 1 else float("nan")

    row.date = _bar_date(last["businessDate"])
    row.open = _round(_finite(last.get("open")))
    row.high = _round(_finite(last.get("high")))
    row.low = _round(_finite(last.get("low")))
    row.close = _round(close)
    row.volume = _round(_finite(last.get("volume")), 0)
    row.supertrend = _round(st)
    row.atr = _round(_finite(last.get("atr")))
    row.trend = trend
    row.signal = signal
    row.volume_ok = volume_ok
    row.flip_buy = flip_buy
    row.flip_sell = flip_sell
    row.rvol = _round(rvol, 2)
    row.vol_sma20 = _round(vol_sma20, 0)
    row.vol_sma50 = _round(vol_sma50, 0)
    row.turnover_sma20 = _round(_finite(last.get("turnover_sma20")), 0)
    row.trailing_stop = _round(trail)
    row.dist_to_trail_pct = _round(dist, 2)
    return row


def meets_liquidity(
    frame: pd.DataFrame,
    settings: Settings,
    fs_row: SymbolFloorsheet | None = None,
) -> bool:
    """20-day OHLCV averages or same-session NEPSE floorsheet turnover/volume."""
    if fs_row is not None:
        if (
            fs_row.quantity >= settings.min_avg_volume
            and fs_row.turnover >= settings.min_avg_turnover_npr
        ):
            return True
    if frame is None or len(frame) < MIN_HISTORY_BARS:
        return False
    volume = frame["volume"].astype(float)
    close = frame["close"].astype(float)
    vol_sma20 = float(volume.rolling(20).mean().iloc[-1])
    turnover_sma20 = float((close * volume).rolling(20).mean().iloc[-1])
    return (
        math.isfinite(vol_sma20)
        and math.isfinite(turnover_sma20)
        and vol_sma20 >= settings.min_avg_volume
        and turnover_sma20 >= settings.min_avg_turnover_npr
    )


def build_universe(
    listed: list[ListedScript],
    ohlcv_map: dict[str, pd.DataFrame],
    settings: Settings,
    *,
    expand: bool = True,
    only: Optional[Iterable[str]] = None,
    floorsheet: FloorsheetSession | None = None,
) -> list[ListedScript]:
    by_symbol = {s.symbol.upper(): s for s in listed}
    if only:
        wanted = [s.strip().upper() for s in only if s.strip()]
        return [
            by_symbol.get(sym, ListedScript(symbol=sym, name=sym)) for sym in wanted
        ]

    elite = elite_basket()
    universe: list[ListedScript] = []
    seen: set[str] = set()
    for symbol in elite:
        script = by_symbol.get(symbol, ListedScript(symbol=symbol, name=symbol))
        universe.append(script)
        seen.add(symbol)

    if not expand:
        return universe

    for script in listed:
        symbol = script.symbol.upper()
        if symbol in seen or not is_ordinary_equity(
            symbol, script.name, script.sector, script.instrument_type
        ):
            continue
        frame = ohlcv_map.get(symbol)
        fs_row = floorsheet.get(symbol) if floorsheet else None
        if frame is None or not meets_liquidity(frame, settings, fs_row):
            continue
        universe.append(script)
        seen.add(symbol)
    return universe


def collect_ohlcv(
    symbols: list[str],
    client: DataClient,
    workers: int,
) -> dict[str, pd.DataFrame]:
    _ = workers  # client batching uses settings.workers
    out = client.ohlcv_many(symbols)
    for symbol, frame in out.items():
        status = f"{len(frame)} bars" if frame is not None and not frame.empty else "empty"
        logger.info("Fetched %s (%s)", symbol, status)
    return out


def update_positions(rows: list[ScanRow], positions: dict) -> dict:
    """Paper-trade book: open on BUY, close on SELL, trail on HOLD."""
    book = dict(positions)
    as_of = next((r.date for r in rows if r.date), nepal_today())
    by_symbol = {r.symbol: r for r in rows}

    for symbol, row in by_symbol.items():
        if row.signal == "BUY" and row.close is not None:
            book[symbol] = {
                "symbol": symbol,
                "entry_date": row.date,
                "entry_price": row.close,
                "trailing_stop": row.trailing_stop,
                "status": "OPEN",
                "updated": as_of,
            }
        elif row.signal == "SELL" and symbol in book and book[symbol].get("status") == "OPEN":
            entry = float(book[symbol].get("entry_price") or 0)
            close = row.close or 0
            pnl_pct = ((close - entry) / entry * 100.0) if entry else None
            book[symbol] = {
                **book[symbol],
                "exit_date": row.date,
                "exit_price": close,
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "status": "CLOSED",
                "updated": as_of,
            }
        elif row.signal == "HOLD" and symbol in book and book[symbol].get("status") == "OPEN":
            book[symbol]["trailing_stop"] = row.trailing_stop
            book[symbol]["updated"] = as_of
    return book


def run_scan(
    *,
    expand: bool = True,
    only: Optional[Iterable[str]] = None,
    settings: Optional[Settings] = None,
    client: Optional[DataClient] = None,
    ohlcv_map: Optional[dict[str, pd.DataFrame]] = None,
    listed: Optional[list[ListedScript]] = None,
    use_cache: bool = True,
) -> ScanReport:
    settings = settings or load_settings()
    client = client or DataClient(settings=settings, use_cache=use_cache)

    floorsheet = FloorsheetSession()
    if client.source == "nepse":
        try:
            floorsheet = client.floorsheet_session(force_refresh=not use_cache)
            logger.info(
                "NEPSE floorsheet %s — %d trades, NPR %.0f turnover, %d symbols",
                floorsheet.business_date,
                floorsheet.total_rows,
                floorsheet.total_turnover,
                floorsheet.symbol_count,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("NEPSE floorsheet unavailable (%s)", exc)

    if listed is None:
        try:
            listed = client.listed_scripts()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Company list unavailable (%s); using elite basket only", exc)
            listed = [ListedScript(symbol=s, name=s) for s in elite_basket()]

    elite = set(elite_basket())
    if only:
        targets = [s.strip().upper() for s in only if s.strip()]
        universe_scripts = [
            next((x for x in listed if x.symbol == s), ListedScript(symbol=s, name=s))
            for s in targets
        ]
        fetch_symbols = targets
    else:
        fetch_symbols = sorted(
            {
                s.symbol.upper()
                for s in listed
                if is_ordinary_equity(
                    s.symbol, s.name, s.sector, s.instrument_type
                )
            }
            | elite
        )
        if not expand:
            fetch_symbols = sorted(elite)
        universe_scripts = None  # resolved after OHLCV

    if ohlcv_map is None:
        ohlcv_map = collect_ohlcv(fetch_symbols, client, settings.workers)

    if universe_scripts is None:
        universe_scripts = build_universe(
            listed,
            ohlcv_map,
            settings,
            expand=expand,
            only=only,
            floorsheet=floorsheet if floorsheet.symbol_count else None,
        )

    rows: list[ScanRow] = []
    skipped: list[str] = []
    for script in universe_scripts:
        frame = ohlcv_map.get(script.symbol, pd.DataFrame())
        fs_row = floorsheet.get(script.symbol) if floorsheet.symbol_count else None
        frame = apply_floorsheet_volume(
            frame, fs_row, floorsheet.business_date if fs_row else ""
        )
        row = evaluate_symbol(
            script.symbol,
            frame,
            name=script.name,
            sector=script.sector,
            elite=script.symbol in elite,
            settings=settings,
        )
        attach_floorsheet(row, fs_row)
        if row.signal == "NONE" and row.note:
            skipped.append(script.symbol)
        rows.append(row)

    buys = sorted([r for r in rows if r.signal == "BUY"], key=lambda r: r.symbol)
    sells = sorted([r for r in rows if r.signal == "SELL"], key=lambda r: r.symbol)
    holds = sorted(
        [r for r in rows if r.signal == "HOLD"],
        key=lambda r: (r.dist_to_trail_pct is None, -(r.dist_to_trail_pct or 0), r.symbol),
    )
    blocked = sorted(
        [r for r in rows if r.signal == "BLOCKED_BUY"], key=lambda r: r.symbol
    )
    scanned = sum(1 for r in rows if r.supertrend is not None)
    as_of = next((r.date for r in rows if r.date), nepal_today())

    report = ScanReport(
        strategy=STRATEGY_NAME,
        as_of=as_of,
        generated_at=datetime.now(timezone.utc).isoformat(),
        universe_count=len(universe_scripts),
        elite_count=sum(1 for r in rows if r.elite),
        dynamic_count=sum(1 for r in rows if not r.elite),
        scanned=scanned,
        skipped=len(skipped),
        buys=buys,
        sells=sells,
        holds=holds,
        blocked_buys=blocked,
        skipped_symbols=skipped,
        data_source=client.source,
        floorsheet_date=floorsheet.business_date,
        floorsheet_rows=floorsheet.total_rows,
        floorsheet_turnover=round(floorsheet.total_turnover, 2),
    )
    return report


def persist_report(
    report: ScanReport,
    settings: Settings,
    listed: Optional[list[ListedScript]] = None,
    positions: Optional[dict] = None,
) -> None:
    from notifier import format_markdown_report, format_telegram

    payload = report.to_dict()
    if report.floorsheet_date:
        payload["floorsheet"] = {
            "business_date": report.floorsheet_date,
            "total_rows": report.floorsheet_rows,
            "total_turnover": report.floorsheet_turnover,
        }
    payload["message"] = format_telegram(report, positions or {})
    save_json(settings.latest_file, payload)
    with open(settings.report_file, "w", encoding="utf-8") as handle:
        handle.write(format_markdown_report(report, positions or {}))
    if listed is not None:
        save_json(settings.universe_file, DataClient.scripts_as_dicts(listed))
    if positions is not None:
        save_json(settings.positions_file, positions)
