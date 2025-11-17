"""Context objects shared across scoring and signal generation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd

from project.data.external import ExternalMetrics
from project.utils.timeframes import ordering_key


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=max(1, period), adjust=False).mean()


@dataclass
class TrendSnapshot:
    trend: float
    slope: float


@dataclass
class AnalysisContext:
    """Aggregates market data across timeframes and external metrics."""

    market_data: Dict[str, Dict[str, pd.DataFrame]]
    external: ExternalMetrics

    def __post_init__(self) -> None:
        self._trend_cache: Dict[Tuple[str, str], TrendSnapshot] = {}

    # --- dataframe helpers -------------------------------------------------
    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        frames = self.market_data.get(timeframe)
        if not frames:
            return None
        frame = frames.get(symbol)
        if frame is None:
            return None
        if not isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.copy()
            frame.index = pd.to_datetime(frame.index, utc=True)
        return frame

    # --- trend / bias helpers ----------------------------------------------
    def _compute_trend(self, symbol: str, timeframe: str) -> TrendSnapshot:
        key = (symbol, timeframe)
        cached = self._trend_cache.get(key)
        if cached is not None:
            return cached

        df = self.get_dataframe(symbol, timeframe)
        if df is None or len(df) < 10:
            snapshot = TrendSnapshot(trend=0.0, slope=0.0)
            self._trend_cache[key] = snapshot
            return snapshot

        close = df["close"].astype(float)
        ema_fast = _ema(close, 12)
        ema_slow = _ema(close, 48)
        diff = ema_fast.iloc[-1] - ema_slow.iloc[-1]
        slope = (
            float((ema_fast.iloc[-1] - ema_fast.iloc[-5]) / max(1e-9, ema_fast.iloc[-5]))
            if len(ema_fast) > 5
            else 0.0
        )
        trend = 1.0 if diff > 0 else -1.0 if diff < 0 else 0.0
        snapshot = TrendSnapshot(trend=trend, slope=slope)
        self._trend_cache[key] = snapshot
        return snapshot

    def trend_bias(self, symbol: str, timeframe: str) -> float:
        return self._compute_trend(symbol, timeframe).trend

    def slope(self, symbol: str, timeframe: str) -> float:
        return self._compute_trend(symbol, timeframe).slope

    def multi_timeframe_confirmation(self, symbol: str, timeframe: str, direction: str) -> Tuple[int, int]:
        """Return (matching, total considered) across higher timeframes."""

        ordered = sorted(self.market_data.keys(), key=ordering_key)
        try:
            index = ordered.index(timeframe)
        except ValueError:
            return (0, 0)

        direction_sign = 1.0 if direction.lower() == "long" else -1.0
        higher_frames: Iterable[str] = ordered[index + 1 :]
        matches = 0
        considered = 0
        for other in higher_frames:
            trend = self.trend_bias(symbol, other)
            if trend == 0:
                continue
            considered += 1
            if trend == direction_sign:
                matches += 1
        return matches, considered

    # --- external metric helpers -----------------------------------------
    def heatmap_bias(self) -> str:
        gauge = self.external.orderbook_heatmap
        if gauge >= 0.65:
            return "bid-heavy"
        if gauge <= 0.35:
            return "ask-heavy"
        return "balanced"


__all__ = ["AnalysisContext"]
