"""Fractal swing point detection."""
from __future__ import annotations

import pandas as pd

from . import SignalResult


def _is_fractal_high(high: pd.Series, index: int, order: int) -> bool:
    left = high.iloc[index - order : index]
    right = high.iloc[index + 1 : index + 1 + order]
    current = high.iloc[index]
    return all(current > left) and all(current > right)


def _is_fractal_low(low: pd.Series, index: int, order: int) -> bool:
    left = low.iloc[index - order : index]
    right = low.iloc[index + 1 : index + 1 + order]
    current = low.iloc[index]
    return all(current < left) and all(current < right)


def fractal_signal(data: pd.DataFrame, order: int = 2) -> SignalResult:
    if data.empty or len(data) < (2 * order + 1):
        return SignalResult("FRACTALS", 0.0, "Not enough candles for fractal detection", {})

    highs = data["high"].reset_index(drop=True)
    lows = data["low"].reset_index(drop=True)

    fractal_high = [False] * len(highs)
    fractal_low = [False] * len(lows)

    for idx in range(order, len(data) - order):
        if _is_fractal_high(highs, idx, order):
            fractal_high[idx] = True
        if _is_fractal_low(lows, idx, order):
            fractal_low[idx] = True

    fractal_df = pd.DataFrame(
        {
            "fractal_high": fractal_high,
            "fractal_low": fractal_low,
        },
        index=data.index,
    )

    recent_window = fractal_df.tail(10)
    score = 0.0
    summary_parts = []
    if recent_window["fractal_low"].any():
        score += 0.5
        summary_parts.append("Recent bullish fractal support")
    if recent_window["fractal_high"].any():
        score -= 0.5
        summary_parts.append("Recent bearish fractal resistance")

    if not summary_parts:
        summary_parts.append("No fresh fractals in last 10 candles")

    return SignalResult(
        name="FRACTALS",
        score=max(min(score, 1.0), -1.0),
        summary="; ".join(summary_parts),
        extra={"fractals": fractal_df},
    )


__all__ = ["fractal_signal"]
