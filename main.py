#!/usr/bin/env python3
"""CLI entrypoint for the NEPSE Supertrend Elite Momentum Basket scanner."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from typing import Optional

from config import STRATEGY_NAME, load_settings
from data_client import DataClient
from notifier import send_latest_report, send_report
from scanner import (
    load_positions,
    persist_report,
    run_scan,
    update_positions,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("supertrend")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=STRATEGY_NAME,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--elite-only",
        action="store_true",
        help="Scan the Elite Trend Compliance basket only (no dynamic liquidity expansion)",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated ticker override (skips universe construction)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Scan and write reports without sending Telegram",
    )
    parser.add_argument(
        "--send-latest",
        action="store_true",
        help="Resend the last saved report without rescanning",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore on-disk OHLCV cache and refetch",
    )
    parser.add_argument(
        "--data-source",
        choices=("nepse", "merolagani"),
        default=None,
        help="OHLCV source: nepse API (default) or merolagani charts",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel NEPSE / merolagani fetches",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    if args.workers is not None:
        settings = replace(settings, workers=max(1, args.workers))
    if args.data_source:
        settings = replace(settings, data_source=args.data_source)

    if args.send_latest:
        return 0 if send_latest_report(settings) else 1

    only = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    client = DataClient(settings=settings, use_cache=not args.no_cache)
    report = run_scan(
        expand=not args.elite_only,
        only=only,
        settings=settings,
        client=client,
        use_cache=not args.no_cache,
    )
    positions = update_positions(
        [*report.buys, *report.sells, *report.holds],
        load_positions(settings.positions_file),
    )
    persist_report(report, settings, positions=positions)

    logger.info(
        "%s %s — BUY %d, SELL %d, HOLD %d, blocked %d (universe %d)",
        STRATEGY_NAME,
        report.as_of,
        len(report.buys),
        len(report.sells),
        len(report.holds),
        len(report.blocked_buys),
        report.universe_count,
    )
    print(open(settings.report_file, encoding="utf-8").read())

    if args.no_telegram:
        return 0
    ok = send_report(report, settings, positions)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
