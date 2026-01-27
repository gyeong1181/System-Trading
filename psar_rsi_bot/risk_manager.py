from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple


@dataclass
class SymbolFilters:
    step_size: float
    min_qty: float
    max_qty: float
    tick_size: float
    min_price: float
    max_price: float
    min_notional: float


class SymbolFilterStore:
    def __init__(self, rest_client, ttl_seconds: int = 300):
        self.rest_client = rest_client
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, SymbolFilters] = {}
        self.last_fetch = 0.0

    async def refresh(self):
        data = await self.rest_client.fetch_exchange_info()
        self.cache = self._parse_exchange_info(data)
        self.last_fetch = time.time()

    async def get(self, symbol: str) -> SymbolFilters:
        if not self.cache or (time.time() - self.last_fetch) > self.ttl_seconds:
            await self.refresh()
        return self.cache[symbol.upper()]

    def _parse_exchange_info(self, data: Dict[str, Any]) -> Dict[str, SymbolFilters]:
        out: Dict[str, SymbolFilters] = {}
        for item in data.get("symbols", []):
            symbol = item.get("symbol")
            if not symbol:
                continue
            filters = {f["filterType"]: f for f in item.get("filters", [])}
            lot = filters.get("LOT_SIZE", {})
            price = filters.get("PRICE_FILTER", {})
            notional = filters.get("MIN_NOTIONAL", {}) or filters.get("NOTIONAL", {})
            out[symbol] = SymbolFilters(
                step_size=float(lot.get("stepSize", 0.001)),
                min_qty=float(lot.get("minQty", 0.0)),
                max_qty=float(lot.get("maxQty", 1e12)),
                tick_size=float(price.get("tickSize", 0.1)),
                min_price=float(price.get("minPrice", 0.0)),
                max_price=float(price.get("maxPrice", 1e12)),
                min_notional=float(notional.get("notional", notional.get("minNotional", 0.0))),
            )
        return out


def normalize_qty_price(
    qty: float, price: float, filters: SymbolFilters
) -> Tuple[float, float, Optional[str]]:
    if filters.step_size > 0:
        qty = math.floor(qty / filters.step_size) * filters.step_size
    if filters.tick_size > 0:
        price = math.floor(price / filters.tick_size) * filters.tick_size

    if qty < filters.min_qty or qty > filters.max_qty:
        return 0.0, 0.0, "qty_out_of_range"
    if price < filters.min_price or price > filters.max_price:
        return 0.0, 0.0, "price_out_of_range"
    if qty * price < filters.min_notional:
        return 0.0, 0.0, "min_notional"
    return qty, price, None


def calc_position_size_fixed_risk(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    leverage: float = 1.0,
    max_notional: Optional[float] = None,
) -> float:
    risk_amount = equity * (risk_pct / 100.0)
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit <= 0:
        return 0.0
    qty = risk_amount / risk_per_unit
    if leverage > 0:
        qty *= max(leverage, 0.01)
    if max_notional:
        qty = min(qty, max_notional / entry_price)
    return max(qty, 0.0)


def compute_required_margin(notional: float, leverage: float, buffer: float) -> float:
    return (notional / max(leverage, 1e-6)) * (1 + buffer)


class AlertCooldown:
    def __init__(self, cooldown_sec: int = 900):
        self.cooldown_sec = cooldown_sec
        self._last: Dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        last = self._last.get(key, 0.0)
        if (now - last) < self.cooldown_sec:
            return False
        self._last[key] = now
        return True


class RiskManager:
    def __init__(
        self,
        rest_client,
        notify_fn: Optional[Callable[[str], None]] = None,
        max_notional_by_symbol: Optional[Dict[str, float]] = None,
        reserve: float = 0.0,
        leverage: float = 1.0,
        risk_pct: float = 1.0,
        margin_buffer: float = 0.05,
        cooldown_sec: int = 900,
    ):
        self.store = SymbolFilterStore(rest_client)
        self.notify_fn = notify_fn
        self.max_notional_by_symbol = max_notional_by_symbol or {}
        self.reserve = reserve
        self.leverage = leverage
        self.risk_pct = risk_pct
        self.margin_buffer = margin_buffer
        self.cooldown = AlertCooldown(cooldown_sec)
        self.open_symbols: Dict[str, bool] = {}

    def mark_open(self, symbol: str):
        self.open_symbols[symbol.upper()] = True

    def mark_closed(self, symbol: str):
        self.open_symbols.pop(symbol.upper(), None)

    def _notify(self, key: str, message: str):
        if self.notify_fn and self.cooldown.allow(key):
            self.notify_fn(message)

    async def size_and_validate(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float,
        equity: float,
        available_balance: float,
    ) -> Tuple[Optional[float], Optional[str]]:
        if self.open_symbols.get(symbol.upper()):
            return None, "position_exists"

        filters = await self.store.get(symbol)
        max_notional = self.max_notional_by_symbol.get(symbol.upper())
        qty = calc_position_size_fixed_risk(
            equity=equity,
            risk_pct=self.risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            leverage=self.leverage,
            max_notional=max_notional,
        )
        if qty <= 0:
            return None, "invalid_qty"

        qty, price, err = normalize_qty_price(qty, entry_price, filters)
        if err:
            self._notify(
                f"order_skip_{symbol}",
                f"[SKIP] {symbol} {err} qty={qty} price={entry_price:.2f}",
            )
            return None, err

        notional = qty * price
        required = compute_required_margin(notional, self.leverage, self.margin_buffer)
        if available_balance < (required + self.reserve):
            self._notify(
                f"balance_{symbol}",
                f"[BAL] {symbol} required={required:.2f} avail={available_balance:.2f} "
                f"reserve={self.reserve:.2f} notional={notional:.2f}",
            )
            return None, "insufficient_balance"
        return qty, None


def parse_max_notional_map(raw: Optional[str]) -> Dict[str, float]:
    if not raw:
        return {}
    out: Dict[str, float] = {}
    for part in raw.split(","):
        if ":" not in part:
            continue
        symbol, value = part.split(":", 1)
        try:
            out[symbol.strip().upper()] = float(value)
        except ValueError:
            continue
    return out
