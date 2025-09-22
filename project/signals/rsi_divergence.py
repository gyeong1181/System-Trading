"""RSI divergence detector."""
from __future__ import annotations

from typing import List

import pandas as pd
from ta.momentum import RSIIndicator

from . import SignalResult


def _pivot_series(series: pd.Series, order: int, mode: str) -> pd.Series:
    window = 2 * order + 1
    rolled = series.rolling(window=window, center=True)
    if mode == "min":
        pivots = series[(series == rolled.min())]
    else:
        pivots = series[(series == rolled.max())]
    return pivots.dropna()


def rsi_divergence_signal(data: pd.DataFrame, rsi_period: int = 14, pivot_order: int = 3) -> SignalResult:
    if data.empty or len(data) < (rsi_period + pivot_order * 2 + 1):
        return SignalResult("RSI_DIVERGENCE", 0.0, "Not enough data for divergence check", {})

    close = data["close"]
    rsi = RSIIndicator(close, window=rsi_period).rsi()
    rsi = rsi.dropna()

    if rsi.empty:
        return SignalResult("RSI_DIVERGENCE", 0.0, "RSI calculation returned no values", {})

    pivot_lows = _pivot_series(close, pivot_order, "min")
    pivot_highs = _pivot_series(close, pivot_order, "max")
    pivot_lows = pivot_lows[pivot_lows.index.isin(rsi.index)]
    pivot_highs = pivot_highs[pivot_highs.index.isin(rsi.index)]

    summaries: List[str] = []
    score = 0.0

    if len(pivot_lows) >= 2:
        last_two = pivot_lows.tail(2)
        price1, price2 = last_two.iloc[0], last_two.iloc[1]
        rsi1, rsi2 = rsi.loc[last_two.index[0]], rsi.loc[last_two.index[1]]
        if price2 < price1 and rsi2 > rsi1:
            score += 1.0
            summaries.append("Bullish divergence detected on lows")

    if len(pivot_highs) >= 2:
        last_two = pivot_highs.tail(2)
        price1, price2 = last_two.iloc[0], last_two.iloc[1]
        rsi1, rsi2 = rsi.loc[last_two.index[0]], rsi.loc[last_two.index[1]]
        if price2 > price1 and rsi2 < rsi1:
            score -= 1.0
            summaries.append("Bearish divergence detected on highs")

    if not summaries:
        summaries.append("No clear RSI divergence")

    score = max(min(score, 1.0), -1.0)

    return SignalResult(
        name="RSI_DIVERGENCE",
        score=score,
        summary="; ".join(summaries),
        extra={"rsi": rsi, "pivot_lows": pivot_lows, "pivot_highs": pivot_highs},
    )


__all__ = ["rsi_divergence_signal"]
