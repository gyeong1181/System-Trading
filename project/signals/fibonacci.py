"""Fibonacci retracement helper."""
from __future__ import annotations

import pandas as pd

from . import SignalResult

LEVELS = (0.236, 0.382, 0.5, 0.618, 0.786)


def fibonacci_levels(data: pd.DataFrame, lookback: int = 120) -> SignalResult:
    if data.empty:
        return SignalResult("FIBONACCI", 0.0, "No data for Fibonacci levels", {})

    window = data.tail(lookback)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    price_range = swing_high - swing_low

    if price_range <= 0:
        return SignalResult("FIBONACCI", 0.0, "Invalid swing range for Fibonacci levels", {})

    levels = {
        f"{level:.3f}": swing_high - price_range * level for level in LEVELS
    }

    latest_close = float(window["close"].iloc[-1])
    position_ratio = (latest_close - swing_low) / price_range

    if position_ratio < 0.3:
        score = 0.5
        summary = "Price near lower retracement (potential support)"
    elif position_ratio > 0.7:
        score = -0.5
        summary = "Price near upper retracement (potential resistance)"
    else:
        score = 0.0
        summary = "Price mid-range between Fibonacci levels"

    return SignalResult(
        name="FIBONACCI",
        score=score,
        summary=summary,
        extra={
            "levels": levels,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "position_ratio": position_ratio,
            "latest_close": latest_close,
        },
    )


__all__ = ["fibonacci_levels"]
