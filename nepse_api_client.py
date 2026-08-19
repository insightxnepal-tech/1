"""NEPSE official API client (nepalstock.com.np via nepseman-api)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Callable, Coroutine, Optional, TypeVar

import pandas as pd
from nepseman_api import NepseClient

from data_client import ListedScript, is_ordinary_equity
from floorsheet import FloorsheetSession, aggregate_floorsheet_rows

logger = logging.getLogger(__name__)

T = TypeVar("T")
_THREAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync code (safe inside ThreadPoolExecutor workers)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = _THREAD_EXECUTOR.submit(asyncio.run, coro)
    return future.result()


def nepse_history_to_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Convert NEPSE price_history rows to a daily OHLCV frame."""
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    rename = {
        "closePrice": "close",
        "highPrice": "high",
        "lowPrice": "low",
        "openPrice": "open",
        "totalTradedQuantity": "volume",
    }
    frame = frame.rename(columns={k: v for k, v in rename.items() if k in frame.columns})
    if "volume" not in frame.columns and "totalTradedQuantity" in frame.columns:
        frame["volume"] = frame["totalTradedQuantity"]
    if "open" not in frame.columns:
        frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    needed = {"businessDate", "high", "low", "close", "volume"}
    missing = needed - set(frame.columns)
    if missing:
        raise ValueError(f"NEPSE history missing columns: {missing}")
    frame["businessDate"] = pd.to_datetime(frame["businessDate"])
    frame = frame.sort_values("businessDate").drop_duplicates("businessDate")
    return frame[["businessDate", "open", "high", "low", "close", "volume"]]


def companies_to_scripts(companies: list[dict]) -> list[ListedScript]:
    scripts: list[ListedScript] = []
    for row in companies:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        name = str(row.get("securityName") or row.get("companyName") or symbol).strip()
        sector = str(row.get("sectorName") or "").strip()
        instrument = str(row.get("instrumentType") or "").strip()
        if instrument and instrument != "Equity":
            continue
        if not is_ordinary_equity(symbol, name, sector):
            continue
        scripts.append(
            ListedScript(
                symbol=symbol,
                name=name,
                sector=sector,
                instrument_type=instrument,
            )
        )
    return scripts


class NepseApiClient:
    """Sync facade over nepseman-api for listed scrips, OHLCV, and floorsheet."""

    def __init__(
        self,
        history_size: int = 500,
        floorsheet_page_size: int = 500,
        max_concurrency: int = 8,
    ):
        self.history_size = history_size
        self.floorsheet_page_size = floorsheet_page_size
        self.max_concurrency = max(1, max_concurrency)

    async def _listed_scripts_async(self) -> list[ListedScript]:
        async with NepseClient() as client:
            companies = await client.company_list()
        return companies_to_scripts(companies)

    async def _ohlcv_async(self, symbol: str) -> pd.DataFrame:
        async with NepseClient() as client:
            rows = await client.price_history(symbol, size=self.history_size)
        return nepse_history_to_ohlcv(rows)

    async def _ohlcv_many_async(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        sem = asyncio.Semaphore(self.max_concurrency)
        out: dict[str, pd.DataFrame] = {}

        async with NepseClient() as client:
            async def one(symbol: str) -> None:
                async with sem:
                    try:
                        rows = await client.price_history(symbol, size=self.history_size)
                        out[symbol] = nepse_history_to_ohlcv(rows)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("NEPSE history failed for %s: %s", symbol, exc)
                        out[symbol] = pd.DataFrame()

            await asyncio.gather(*(one(symbol) for symbol in symbols))

        return out

    async def _floorsheet_async(self) -> FloorsheetSession:
        page = 1
        all_rows: list[dict] = []
        async with NepseClient() as client:
            while True:
                rows = await client.floor_sheet(page=page, size=self.floorsheet_page_size)
                if not rows:
                    break
                all_rows.extend(rows)
                if len(rows) < self.floorsheet_page_size:
                    break
                page += 1
        logger.info(
            "NEPSE floorsheet fetched %d trades across %d page(s)",
            len(all_rows),
            page,
        )
        return aggregate_floorsheet_rows(all_rows)

    def listed_scripts(self) -> list[ListedScript]:
        return run_async(self._listed_scripts_async())

    def ohlcv(self, symbol: str) -> pd.DataFrame:
        return run_async(self._ohlcv_async(symbol.upper()))

    def ohlcv_many(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}
        return run_async(self._ohlcv_many_async([s.upper() for s in symbols]))

    def floorsheet_session(self) -> FloorsheetSession:
        return run_async(self._floorsheet_async())
