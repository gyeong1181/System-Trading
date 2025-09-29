"""Dataclasses describing trading signals."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Signal:
    """A single trading signal produced by the engine."""

    symbol: str
    direction: str
    timeframe: str
    score: int
    grade: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_duplicate: bool = False
    is_optimal: bool = False
    signature_hits: int = 1
    direction_hits: int = 1

    def signature(self) -> str:
        """Stable representation used for duplicate detection."""

        pivot = self.metadata.get("pattern")
        if pivot is None:
            pivot = round(float(self.metadata.get("momentum", 0.0)), 6)
        return f"{self.symbol}|{self.timeframe}|{self.direction}|{pivot}"

    @property
    def direction_label(self) -> str:
        return "롱" if self.direction.lower() == "long" else "숏"


__all__ = ["Signal"]
