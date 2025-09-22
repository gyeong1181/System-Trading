"""EMA trend filter."""
from __future__ import annotations

import pandas as pd

from . import SignalResult


def ema_signal(data: pd.DataFrame, period: int = 200) -> SignalResult:
    """Return an EMA-based directional bias."""

    if data.empty:
        return SignalResult("EMA", 0.0, "No data available for EMA calculation", {})

    ema = data["close"].ewm(span=period, adjust=False).mean()
    latest_close = data["close"].iloc[-1]
    latest_ema = ema.iloc[-1]

    if latest_close > latest_ema:
        score = 1.0
        summary = f"Bullish: close {latest_close:.2f} above EMA{period} {latest_ema:.2f}"
    elif latest_close < latest_ema:
        score = -1.0
        summary = f"Bearish: close {latest_close:.2f} below EMA{period} {latest_ema:.2f}"
    else:
        score = 0.0
        summary = f"Neutral: close {latest_close:.2f} equals EMA{period}"

    return SignalResult(
        name="EMA",
        score=score,
        summary=summary,
        extra={"ema": ema, "latest": {"close": latest_close, "ema": latest_ema}},
    )


__all__ = ["ema_signal"]
