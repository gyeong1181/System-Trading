from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TradeSignal:
    strategy_id: str
    symbol: str
    timeframe: str
    action: str
    side: str
    bar_time: datetime
    price: float
    stop_price: float | None = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def dedup_key(self) -> str:
        stamp = self.bar_time.strftime("%Y%m%d%H%M%S")
        return f"{self.strategy_id}-{self.symbol}-{self.action}-{self.side}-{stamp}"


@dataclass
class PositionState:
    symbol: str
    strategy_id: str
    mode: str
    side: str
    qty: float
    entry_price: float
    stop_price: float | None
    opened_at: datetime
    updated_at: datetime
    status: str = "open"
    risk_pct: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionOrder:
    client_order_id: str
    symbol: str
    strategy_id: str
    mode: str
    action: str
    side: str
    qty: float
    reference_price: float
    stop_price: float | None
    reason: str
    signal_time: datetime
    reduce_only: bool = False
    leverage: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    reason: str
    order: ExecutionOrder | None = None


@dataclass
class StrategyResult:
    strategy_id: str
    symbol: str
    timeframe: str
    params: dict[str, Any]
    classification: str
    score: float
    metrics: dict[str, float]
    monthly_returns: list[dict[str, Any]]
    windows: list[dict[str, Any]]
