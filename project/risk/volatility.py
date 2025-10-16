"""Volatility-based guards for the signal engine."""
from __future__ import annotations


class AtrGuard:
    """Blocks signals when ATR percentage exceeds configured thresholds."""

    def __init__(self, *, hold_threshold: float, release_threshold: float | None = None) -> None:
        self._hold_threshold = float(hold_threshold)
        self._release_threshold = float(release_threshold or hold_threshold * 0.75)

    def should_block(self, atr_pct: float) -> bool:
        return float(atr_pct or 0.0) >= self._hold_threshold

    def is_recovering(self, atr_pct: float) -> bool:
        return float(atr_pct or 0.0) <= self._release_threshold


__all__ = ["AtrGuard"]
