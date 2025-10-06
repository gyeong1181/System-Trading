"""Utility helpers for timeframe string manipulation."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=32)
def to_minutes(value: str) -> int:
    """Convert timeframe representations (5m/1h/1d) to minutes."""

    cleaned = (value or "").strip().lower()
    if cleaned.endswith("m"):
        return max(1, int(cleaned[:-1]))
    if cleaned.endswith("h"):
        return max(1, int(cleaned[:-1]) * 60)
    if cleaned.endswith("d"):
        return max(1, int(cleaned[:-1]) * 60 * 24)
    if cleaned.endswith("w"):
        return max(1, int(cleaned[:-1]) * 60 * 24 * 7)
    return max(1, int(cleaned or 0))


@lru_cache(maxsize=32)
def ordering_key(value: str) -> int:
    """Return an ordering key suitable for sorting timeframes."""

    return to_minutes(value)


__all__ = ["to_minutes", "ordering_key"]
