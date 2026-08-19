"""Intraday Supertrend live scan — Telegram on new BUY / SELL only."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from config import (
    LIVE_CLOSED_POLL_SECONDS,
    LIVE_POLL_SECONDS,
    STRATEGY_NAME,
    Settings,
    elite_basket,
    load_settings,
)
from data_client import DataClient, ListedScript
from notifier import format_live_alerts, send_telegram
from scanner import (
    ScanRow,
    evaluate_symbol,
    load_json,
    nepal_today,
    save_json,
    update_positions,
    load_positions,
)

logger = logging.getLogger(__name__)
KATHMANDU = ZoneInfo("Asia/Kathmandu")
SESSION_OPEN = dt_time(11, 0)
SESSION_CLOSE = dt_time(15, 5)


@dataclass(frozen=True)
class LiveQuote:
    symbol: str
    business_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float = 0.0
    last_updated: str = ""
    source: str = "today_price"


def _num(row: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def parse_live_quote(row: dict, source: str) -> LiveQuote | None:
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    close = _num(
        row,
        "lastTradedPrice",
        "ltp",
        "lastUpdatedPrice",
        "closePrice",
        "lastTradePrice",
    )
    if close <= 0:
        return None
    high = _num(row, "highPrice", "high", default=close) or close
    low = _num(row, "lowPrice", "low", default=close) or close
    open_px = _num(row, "openPrice", "open", default=close) or close
    volume = _num(
        row,
        "totalTradedQuantity",
        "totalTradeQuantity",
        "quantity",
        "volume",
    )
    turnover = _num(row, "totalTradedValue", "volume", "turnover")
    date = str(
        row.get("businessDate")
        or row.get("lastUpdatedDate")
        or row.get("asOf")
        or nepal_today()
    )[:10]
    updated = str(
        row.get("lastUpdatedTime")
        or row.get("lastUpdatedDateTime")
        or row.get("lastTradedTime")
        or ""
    )
    return LiveQuote(
        symbol=symbol,
        business_date=date,
        open=open_px,
        high=max(high, close, open_px),
        low=min(low, close, open_px) if min(low, close, open_px) > 0 else close,
        close=close,
        volume=volume,
        turnover=turnover,
        last_updated=updated,
        source=source,
    )


def merge_quotes(live_rows: list[dict], today_rows: list[dict]) -> dict[str, LiveQuote]:
    """Prefer live_market ticks; fill gaps from today_price."""
    quotes: dict[str, LiveQuote] = {}
    for row in today_rows:
        parsed = parse_live_quote(row, "today_price")
        if parsed:
            quotes[parsed.symbol] = parsed
    for row in live_rows:
        parsed = parse_live_quote(row, "live_market")
        if parsed:
            quotes[parsed.symbol] = parsed
    return quotes


def overlay_live_bar(frame: pd.DataFrame, quote: LiveQuote) -> pd.DataFrame:
    """Replace or append today's forming OHLC bar from a live quote."""
    if frame is None or frame.empty:
        return pd.DataFrame(
            [
                {
                    "businessDate": pd.Timestamp(quote.business_date),
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "close": quote.close,
                    "volume": quote.volume,
                }
            ]
        )
    out = frame.copy().sort_values("businessDate").reset_index(drop=True)
    last_date = pd.Timestamp(out["businessDate"].iloc[-1]).strftime("%Y-%m-%d")
    bar = {
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "close": quote.close,
        "volume": quote.volume,
    }
    if last_date == quote.business_date:
        for col, value in bar.items():
            out.loc[out.index[-1], col] = value
        return out
    extra = {**bar, "businessDate": pd.Timestamp(quote.business_date)}
    return pd.concat([out, pd.DataFrame([extra])], ignore_index=True)


def market_is_open(status: dict) -> bool:
    flag = str(status.get("isOpen") or status.get("status") or "").upper()
    return flag in {"OPEN", "TRUE", "1"}


def alert_key(row: ScanRow) -> str:
    return f"{row.symbol}|{row.date}|{row.signal}"


def load_alert_state(path: str) -> dict:
    data = load_json(path, {"sent": {}})
    if not isinstance(data, dict):
        return {"sent": {}}
    data.setdefault("sent", {})
    return data


def new_buy_sell_alerts(rows: list[ScanRow], state: dict) -> list[ScanRow]:
    sent = state.get("sent") or {}
    fresh: list[ScanRow] = []
    for row in rows:
        if row.signal not in {"BUY", "SELL"}:
            continue
        key = alert_key(row)
        if key in sent:
            continue
        fresh.append(row)
        sent[key] = {
            "symbol": row.symbol,
            "signal": row.signal,
            "date": row.date,
            "close": row.close,
            "at": datetime.now(KATHMANDU).isoformat(),
        }
    state["sent"] = sent
    return fresh


def evaluate_live_universe(
    ohlcv_map: dict[str, pd.DataFrame],
    quotes: dict[str, LiveQuote],
    scripts: list[ListedScript],
    settings: Settings,
) -> list[ScanRow]:
    elite = set(elite_basket())
    rows: list[ScanRow] = []
    for script in scripts:
        frame = ohlcv_map.get(script.symbol)
        if frame is None or frame.empty:
            continue
        quote = quotes.get(script.symbol)
        live_frame = overlay_live_bar(frame, quote) if quote else frame
        row = evaluate_symbol(
            script.symbol,
            live_frame,
            name=script.name,
            sector=script.sector,
            elite=script.symbol in elite,
            settings=settings,
        )
        if quote:
            if row.note == "":
                row.note = f"live {quote.source}"
            row.fs_quantity = quote.volume
            row.fs_turnover = round(quote.turnover, 2) if quote.turnover else None
        rows.append(row)
    return rows


def in_trading_window(now: datetime | None = None) -> bool:
    now = now or datetime.now(KATHMANDU)
    if now.weekday() in {4, 5}:
        return False
    return SESSION_OPEN <= now.time() <= SESSION_CLOSE


def run_live(
    *,
    settings: Optional[Settings] = None,
    client: Optional[DataClient] = None,
    elite_only: bool = True,
    poll_seconds: int = LIVE_POLL_SECONDS,
    closed_poll_seconds: int = LIVE_CLOSED_POLL_SECONDS,
    once: bool = False,
    until_close: bool = True,
    max_runtime_seconds: Optional[int] = None,
    send: bool = True,
    snapshot_fn: Optional[Callable[[], tuple[dict, list[dict], list[dict]]]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[ScanRow]:
    """
    Poll NEPSE live/today prices, overlay the forming candle, Telegram BUY/SELL.

    Forming-bar flips are labeled live; they can reverse before the official close.
    """
    settings = settings or load_settings()
    client = client or DataClient(settings=settings, use_cache=True)
    symbols = list(elite_basket())
    listed = [ListedScript(symbol=s, name=s) for s in symbols]
    try:
        remote = {s.symbol: s for s in client.listed_scripts()}
        listed = [remote.get(s, ListedScript(symbol=s, name=s)) for s in symbols]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Listed scripts unavailable: %s", exc)

    logger.info("Loading OHLCV for %d live symbols (elite_only=%s)", len(symbols), elite_only)
    ohlcv_map = client.ohlcv_many(symbols)
    state = load_alert_state(settings.live_state_file)
    started = time.monotonic()
    all_fresh: list[ScanRow] = []
    last_open: bool | None = None

    if snapshot_fn is None:
        def snapshot_fn() -> tuple[dict, list[dict], list[dict]]:
            return client._nepse_client().market_snapshot()

    if send:
        send_telegram(
            f"📡 *{STRATEGY_NAME} — LIVE watch*\n"
            f"Polling NEPSE `live_market` / `today_price` every {poll_seconds}s.\n"
            f"Telegram fires only on new *BUY* or *SELL* (Supertrend 10, 3.0).\n"
            f"_Forming candle — not an EOD confirmation._",
            settings=settings,
        )

    while True:
        if max_runtime_seconds is not None and (time.monotonic() - started) >= max_runtime_seconds:
            logger.info("Live watch hit max runtime")
            break

        try:
            status, live_rows, today_rows = snapshot_fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Live snapshot failed: %s", exc)
            if once:
                break
            sleep_fn(closed_poll_seconds)
            continue

        open_now = market_is_open(status)
        quotes = merge_quotes(live_rows or [], today_rows or [])
        rows = evaluate_live_universe(ohlcv_map, quotes, listed, settings)
        fresh = new_buy_sell_alerts(rows, state)
        save_json(settings.live_state_file, state)
        if fresh:
            all_fresh.extend(fresh)
            logger.info(
                "LIVE alerts: %s",
                ", ".join(f"{r.signal} {r.symbol}@{r.close}" for r in fresh),
            )
            if send:
                send_telegram(format_live_alerts(fresh, status, open_now), settings=settings)
                positions = update_positions(fresh, load_positions(settings.positions_file))
                save_json(settings.positions_file, positions)

        buys = sum(1 for r in rows if r.signal == "BUY")
        sells = sum(1 for r in rows if r.signal == "SELL")
        holds = sum(1 for r in rows if r.signal == "HOLD")
        logger.info(
            "Live tick market=%s quotes=%d BUY=%d SELL=%d HOLD=%d new_alerts=%d",
            status.get("isOpen"),
            len(quotes),
            buys,
            sells,
            holds,
            len(fresh),
        )

        if last_open is False and open_now and send:
            send_telegram(
                f"🟢 *NEPSE OPEN* — live Supertrend watch is on `{nepal_today()}`.",
                settings=settings,
            )
        last_open = open_now

        if once:
            break
        if until_close and last_open is True and not open_now and not in_trading_window():
            logger.info("Market closed and outside window — stopping live watch")
            if send:
                send_telegram(
                    f"⏹ *LIVE watch stopped* — NEPSE closed (`{status.get('asOf', nepal_today())}`).",
                    settings=settings,
                )
            break

        sleep_fn(poll_seconds if open_now else closed_poll_seconds)

    return all_fresh
