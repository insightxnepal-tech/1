"""Runtime configuration for the NEPSE Supertrend Elite Momentum Basket."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final

from dotenv import load_dotenv

load_dotenv()

STRATEGY_NAME: Final[str] = "NEPSE Supertrend Elite Momentum Basket"

# Supertrend(ATR-10, multiplier 3.0) — TradingView / KivancOzbilgic defaults.
SUPERTREND_PERIOD: Final[int] = 10
SUPERTREND_MULTIPLIER: Final[float] = 3.0

VOLUME_SMA_SHORT: Final[int] = 20
VOLUME_SMA_LONG: Final[int] = 50
RVOL_THRESHOLD: Final[float] = 1.2

# Dynamic-universe liquidity floors (20-session averages).
MIN_AVG_VOLUME: Final[float] = 5_000.0
MIN_AVG_TURNOVER_NPR: Final[float] = 500_000.0

MIN_HISTORY_BARS: Final[int] = VOLUME_SMA_LONG + SUPERTREND_PERIOD
HISTORY_CALENDAR_DAYS: Final[int] = 800
NEPSE_HISTORY_SIZE: Final[int] = 500
FLOORSHEET_PAGE_SIZE: Final[int] = 500
MAX_WORKERS: Final[int] = 8
REQUEST_TIMEOUT: Final[int] = 25
RETRY_COUNT: Final[int] = 3

MEROLAGANI_ORIGIN: Final[str] = "https://merolagani.com"
COMPANY_LIST_URL: Final[str] = f"{MEROLAGANI_ORIGIN}/CompanyList.aspx"
CHART_URL: Final[str] = f"{MEROLAGANI_ORIGIN}/handlers/TechnicalChartHandler.ashx"

SKIP_NAME_FRAGMENTS: Final[tuple[str, ...]] = (
    "Mutual Fund",
    "Debenture",
    "Bond",
    "Promoter",
    "Preference",
)

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Historically verified Elite Trend Compliance basket.
DEFAULT_ELITE_BASKET: Final[tuple[str, ...]] = (
    "HDL",
    "NLG",
    "CIT",
    "SHEL",
    "FMDBL",
    "SIKLES",
    "MAKAR",
    "SMJC",
    "BHDC",
    "USHL",
    "MMKJL",
    "MSHL",
    "ANLB",
    "RADHI",
    "MFIL",
)

TELEGRAM_CHUNK_SIZE: Final[int] = 4000
TELEGRAM_DEFAULT_CHAT_ID: Final[str] = "8563709547"


def _csv_symbols(raw: str) -> tuple[str, ...]:
    return tuple(s.strip().upper() for s in raw.split(",") if s.strip())


def elite_basket() -> tuple[str, ...]:
    extra = _csv_symbols(os.getenv("ELITE_EXTRA_SYMBOLS", ""))
    seen: set[str] = set()
    ordered: list[str] = []
    for symbol in (*DEFAULT_ELITE_BASKET, *extra):
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return tuple(ordered)


@dataclass(frozen=True)
class Settings:
    """Process settings loaded from the environment."""

    telegram_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "").strip()
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv(
            "TELEGRAM_CHAT_ID", TELEGRAM_DEFAULT_CHAT_ID
        ).strip()
    )
    positions_file: str = field(
        default_factory=lambda: os.getenv(
            "SUPERTREND_POSITIONS_FILE", "supertrend_positions.json"
        )
    )
    latest_file: str = field(
        default_factory=lambda: os.getenv(
            "SUPERTREND_LATEST_FILE", "supertrend_scan_latest.json"
        )
    )
    report_file: str = field(
        default_factory=lambda: os.getenv(
            "SUPERTREND_REPORT_FILE", "supertrend_scan_report.md"
        )
    )
    universe_file: str = field(
        default_factory=lambda: os.getenv(
            "SUPERTREND_UNIVERSE_FILE", "supertrend_universe.json"
        )
    )
    cache_dir: str = field(
        default_factory=lambda: os.getenv("SUPERTREND_CACHE_DIR", "data/ohlcv")
    )
    floorsheet_cache_file: str = field(
        default_factory=lambda: os.getenv(
            "SUPERTREND_FLOORSHEET_CACHE", "data/floorsheet_latest.json"
        )
    )
    data_source: str = field(
        default_factory=lambda: os.getenv("SUPERTREND_DATA_SOURCE", "nepse").strip().lower()
    )
    workers: int = field(
        default_factory=lambda: int(os.getenv("SUPERTREND_WORKERS", str(MAX_WORKERS)))
    )
    history_calendar_days: int = HISTORY_CALENDAR_DAYS
    min_avg_volume: float = MIN_AVG_VOLUME
    min_avg_turnover_npr: float = MIN_AVG_TURNOVER_NPR
    rvol_threshold: float = RVOL_THRESHOLD
    supertrend_period: int = SUPERTREND_PERIOD
    supertrend_multiplier: float = SUPERTREND_MULTIPLIER


def load_settings() -> Settings:
    return Settings()
