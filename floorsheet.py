"""Aggregate NEPSE floorsheet trades into per-symbol session stats."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class SymbolFloorsheet:
    symbol: str
    quantity: float
    turnover: float
    trades: int
    vwap: float


@dataclass
class FloorsheetSession:
    business_date: str = ""
    total_rows: int = 0
    total_turnover: float = 0.0
    symbol_count: int = 0
    by_symbol: dict[str, SymbolFloorsheet] = field(default_factory=dict)

    def get(self, symbol: str) -> SymbolFloorsheet | None:
        return self.by_symbol.get(symbol.upper())

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["by_symbol"] = {k: asdict(v) for k, v in self.by_symbol.items()}
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "FloorsheetSession":
        by_symbol = {
            symbol: SymbolFloorsheet(**row)
            for symbol, row in (payload.get("by_symbol") or {}).items()
        }
        return cls(
            business_date=str(payload.get("business_date") or ""),
            total_rows=int(payload.get("total_rows") or 0),
            total_turnover=float(payload.get("total_turnover") or 0.0),
            symbol_count=int(payload.get("symbol_count") or len(by_symbol)),
            by_symbol=by_symbol,
        )


def aggregate_floorsheet_rows(rows: list[dict]) -> FloorsheetSession:
    """Roll up raw NEPSE floorsheet contract rows by stock symbol."""
    totals: dict[str, dict[str, float]] = {}
    business_date = ""
    for row in rows:
        symbol = str(row.get("stockSymbol") or "").strip().upper()
        if not symbol:
            continue
        business_date = str(row.get("businessDate") or business_date)
        qty = float(row.get("contractQuantity") or 0)
        amount = float(row.get("contractAmount") or 0)
        bucket = totals.setdefault(symbol, {"qty": 0.0, "amt": 0.0, "trades": 0.0})
        bucket["qty"] += qty
        bucket["amt"] += amount
        bucket["trades"] += 1

    by_symbol: dict[str, SymbolFloorsheet] = {}
    total_turnover = 0.0
    for symbol, bucket in totals.items():
        qty = bucket["qty"]
        amt = bucket["amt"]
        trades = int(bucket["trades"])
        vwap = (amt / qty) if qty else 0.0
        by_symbol[symbol] = SymbolFloorsheet(
            symbol=symbol,
            quantity=qty,
            turnover=amt,
            trades=trades,
            vwap=vwap,
        )
        total_turnover += amt

    return FloorsheetSession(
        business_date=business_date,
        total_rows=len(rows),
        total_turnover=total_turnover,
        symbol_count=len(by_symbol),
        by_symbol=by_symbol,
    )
