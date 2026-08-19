"""Telegram + markdown reporting for Supertrend Elite signals."""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from config import STRATEGY_NAME, TELEGRAM_CHUNK_SIZE, Settings, load_settings
from scanner import ScanReport, ScanRow

logger = logging.getLogger(__name__)


def _rvol(row: ScanRow) -> str:
    return f"{row.rvol:.2f}x" if row.rvol is not None else "n/a"


def _price(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _pnl_line(row: ScanRow, positions: dict) -> str:
    pos = positions.get(row.symbol) or {}
    entry = pos.get("entry_price")
    if not isinstance(entry, (int, float)) or not entry or row.close is None:
        return ""
    pnl = (row.close - float(entry)) / float(entry) * 100.0
    entered = pos.get("entry_date", "?")
    return f" | P/L {pnl:+.1f}% since {entered}"


def format_telegram(report: ScanReport, positions: Optional[dict] = None) -> str:
    positions = positions or {}
    fs_line = ""
    if report.floorsheet_date:
        fs_line = (
            f"NEPSE floorsheet `{report.floorsheet_date}` · "
            f"{report.floorsheet_rows:,} trades · "
            f"NPR {report.floorsheet_turnover:,.0f} turnover"
        )
    lines = [
        f"📈 *{STRATEGY_NAME}*",
        f"Session `{report.as_of}` · Supertrend(10, 3.0) · source `{report.data_source}`",
    ]
    if fs_line:
        lines.append(fs_line)
    lines.append("")

    if report.buys:
        lines.append(f"🟢 *BUY — Supertrend green flip* ({len(report.buys)})")
        lines.append("_Close flipped above Supertrend + volume filter_")
        lines.append("")
        for row in report.buys:
            lines.append(f"• *{row.symbol}* @ Rs {_price(row.close)}")
            fs_bits = ""
            if row.fs_turnover is not None:
                fs_bits = f" · FS NPR {row.fs_turnover:,.0f} ({row.fs_trades or 0} trades)"
            lines.append(
                f"  Trail SL {_price(row.trailing_stop)} · "
                f"cushion {_pct(row.dist_to_trail_pct)} · RVOL {_rvol(row)}{fs_bits}"
            )
            if row.elite:
                lines.append("  Elite basket")
            lines.append("")
    else:
        lines.append("🟢 *BUY:* none")
        lines.append("")

    if report.sells:
        lines.append(f"🔴 *SELL / FULL EXIT — Supertrend red flip* ({len(report.sells)})")
        lines.append("_Close below the green Supertrend trailing stop_")
        lines.append("")
        for row in report.sells:
            extra = _pnl_line(row, positions)
            lines.append(f"• *{row.symbol}* @ Rs {_price(row.close)}{extra}")
            lines.append(f"  Supertrend {_price(row.supertrend)}")
            lines.append("")
    else:
        lines.append("🔴 *SELL / FULL EXIT:* none")
        lines.append("")

    if report.holds:
        lines.append(f"🟢 *ACTIVE TREND / HOLD* ({len(report.holds)})")
        lines.append("_Established Supertrend bullish · distance to trail_")
        lines.append("")
        for row in report.holds:
            badge = " · Elite" if row.elite else ""
            fs_bits = ""
            if row.fs_turnover is not None:
                fs_bits = f" · FS NPR {row.fs_turnover:,.0f}"
            lines.append(
                f"• *{row.symbol}* @ Rs {_price(row.close)} · "
                f"SL {_price(row.trailing_stop)} · {_pct(row.dist_to_trail_pct)}{badge}{fs_bits}"
            )
        lines.append("")
    else:
        lines.append("🟢 *ACTIVE TREND / HOLD:* none")
        lines.append("")

    if report.blocked_buys:
        lines.append(f"🟡 *GREEN FLIP, VOLUME BLOCKED* ({len(report.blocked_buys)})")
        lines.append("_Need 20d vol SMA > 50d SMA or RVOL > 1.2x_")
        lines.append("")
        for row in report.blocked_buys:
            lines.append(
                f"• *{row.symbol}* @ Rs {_price(row.close)} · RVOL {_rvol(row)}"
            )
        lines.append("")

    lines.append(
        f"_Universe {report.universe_count} "
        f"({report.elite_count} elite + {report.dynamic_count} dynamic) · "
        f"scanned {report.scanned} · skipped {report.skipped}._"
    )
    lines.append("_Not financial advice. Unofficial NEPSE API data._")
    return "\n".join(lines).strip() + "\n"


def format_markdown_report(
    report: ScanReport, positions: Optional[dict] = None
) -> str:
    positions = positions or {}
    lines = [
        f"# {STRATEGY_NAME} — {report.as_of}",
        "",
        f"Data source: **{report.data_source}** · Supertrend period **10**, multiplier **3.0**, Wilder ATR-10.",
    ]
    if report.floorsheet_date:
        lines.append(
            f"NEPSE floorsheet **{report.floorsheet_date}**: "
            f"{report.floorsheet_rows:,} trades, NPR {report.floorsheet_turnover:,.0f} turnover."
        )
    lines += [
        "BUY = green flip + (20-day volume SMA > 50-day SMA **or** RVOL > 1.2).",
        "SELL = Supertrend red flip. Trailing stop = current green Supertrend line.",
        "",
        f"- Universe: **{report.universe_count}** "
        f"({report.elite_count} elite, {report.dynamic_count} dynamic)",
        f"- Scanned: **{report.scanned}**",
        f"- Skipped: **{report.skipped}**",
        f"- BUY: **{len(report.buys)}**",
        f"- SELL: **{len(report.sells)}**",
        f"- HOLD: **{len(report.holds)}**",
        f"- Volume-blocked green flips: **{len(report.blocked_buys)}**",
        "",
        "## BUY",
        "",
    ]
    if report.buys:
        lines.append(
            "| Symbol | Elite | Close | Supertrend / trail | Cushion | RVOL | Vol SMA20/50 |"
        )
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for row in report.buys:
            lines.append(
                f"| {row.symbol} | {'yes' if row.elite else ''} | "
                f"{_price(row.close)} | {_price(row.trailing_stop)} | "
                f"{_pct(row.dist_to_trail_pct)} | {_rvol(row)} | "
                f"{_price(row.vol_sma20)} / {_price(row.vol_sma50)} |"
            )
    else:
        lines.append("None.")

    lines += ["", "## SELL / FULL EXIT", ""]
    if report.sells:
        lines.append("| Symbol | Close | Supertrend | Paper P/L |")
        lines.append("| --- | ---: | ---: | --- |")
        for row in report.sells:
            extra = _pnl_line(row, positions).strip(" |") or "—"
            lines.append(
                f"| {row.symbol} | {_price(row.close)} | {_price(row.supertrend)} | {extra} |"
            )
    else:
        lines.append("None.")

    lines += ["", "## ACTIVE TREND / HOLD", ""]
    if report.holds:
        lines.append("| Symbol | Elite | Close | Trailing SL | Distance | RVOL |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for row in report.holds:
            lines.append(
                f"| {row.symbol} | {'yes' if row.elite else ''} | "
                f"{_price(row.close)} | {_price(row.trailing_stop)} | "
                f"{_pct(row.dist_to_trail_pct)} | {_rvol(row)} |"
            )
    else:
        lines.append("None.")

    if report.blocked_buys:
        lines += ["", "## Green flips blocked by volume", ""]
        lines.append("| Symbol | Close | RVOL | Vol SMA20 | Vol SMA50 |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for row in report.blocked_buys:
            lines.append(
                f"| {row.symbol} | {_price(row.close)} | {_rvol(row)} | "
                f"{_price(row.vol_sma20)} | {_price(row.vol_sma50)} |"
            )

    if report.skipped_symbols:
        lines += ["", "## Skipped", "", ", ".join(report.skipped_symbols)]

    lines += ["", "_Not financial advice. Unofficial NEPSE API data._", ""]
    return "\n".join(lines)


def send_telegram(
    text: str,
    settings: Optional[Settings] = None,
    token: str = "",
    chat_id: str = "",
) -> bool:
    settings = settings or load_settings()
    token = token or settings.telegram_token
    chat_id = chat_id or settings.telegram_chat_id
    if not token:
        logger.warning(
            "Telegram skipped: TELEGRAM_TOKEN not set. "
            "Chat id is ready; add a live BotFather token to send."
        )
        return False
    if not chat_id:
        logger.warning("Telegram skipped: TELEGRAM_CHAT_ID not set.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for i in range(0, len(text), TELEGRAM_CHUNK_SIZE):
        chunk = text[i : i + TELEGRAM_CHUNK_SIZE]
        try:
            res = requests.post(
                url,
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
                timeout=20,
            )
            logger.info("Telegram status %s: %s", res.status_code, res.text[:200])
            if res.status_code != 200:
                res = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=20,
                )
                logger.info(
                    "Telegram plain status %s: %s", res.status_code, res.text[:200]
                )
                if res.status_code != 200:
                    ok = False
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram send error: %s", exc)
            ok = False
    return ok


def send_telegram_document(
    path: str,
    caption: str = "",
    settings: Optional[Settings] = None,
) -> bool:
    settings = settings or load_settings()
    token = settings.telegram_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id or not os.path.exists(path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(path, "rb") as handle:
            res = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": (os.path.basename(path), handle, "text/markdown")},
                timeout=30,
            )
        logger.info("Telegram document status %s: %s", res.status_code, res.text[:200])
        return res.status_code == 200
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram document error: %s", exc)
        return False


def send_report(report: ScanReport, settings: Settings, positions: Optional[dict] = None) -> bool:
    text = format_telegram(report, positions or {})
    ok = send_telegram(text, settings=settings)
    caption = f"{STRATEGY_NAME} — {report.as_of}"
    ok_doc = send_telegram_document(settings.report_file, caption=caption, settings=settings)
    if not ok:
        logger.warning("Telegram message delivery failed.")
    if not ok_doc:
        logger.warning("Telegram document delivery failed (message may still have been sent).")
    return ok


def send_latest_report(settings: Optional[Settings] = None) -> bool:
    from scanner import load_json

    settings = settings or load_settings()
    payload = load_json(settings.latest_file, {})
    if not payload:
        logger.error("No scan to send: %s missing or empty.", settings.latest_file)
        return False
    text = payload.get("message") or ""
    if not text:
        logger.error("Latest scan has no Telegram message body.")
        return False
    ok = send_telegram(text, settings=settings)
    caption = f"{STRATEGY_NAME} — {payload.get('as_of', '')}"
    send_telegram_document(settings.report_file, caption=caption, settings=settings)
    return ok
