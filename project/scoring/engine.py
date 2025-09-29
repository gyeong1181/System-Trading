"""Functions for turning market data into numerical scores."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScoreComponents:
    """Breakdown of the numerical score for diagnostics."""

    momentum: float
    trend_strength: float
    volatility: float
    volume_ratio: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "momentum": self.momentum,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "volume_ratio": self.volume_ratio,
        }


def _safe_pct_change(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    prev = values.iloc[-2]
    curr = values.iloc[-1]
    if prev == 0:
        return 0.0
    return float((curr - prev) / prev)


def _rolling_std(series: pd.Series, window: int) -> float:
    if len(series) < window:
        return float(series.std(ddof=0) or 0.0)
    return float(series.pct_change().rolling(window).std(ddof=0).iloc[-1] or 0.0)


def _volume_ratio(series: pd.Series, window: int = 30) -> float:
    if len(series) < window:
        return 0.0
    recent = float(series.iloc[-1])
    baseline = float(series.rolling(window).mean().iloc[-1] or 0.0)
    if baseline == 0.0:
        return 0.0
    return recent / baseline


def calculate_score(df: pd.DataFrame) -> Tuple[int, ScoreComponents]:
    """Return a 0-99 score and diagnostic components for the given data frame."""

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ma_window = min(55, max(20, len(close) // 4))
    momentum = _safe_pct_change(close)
    rolling_mean = close.rolling(ma_window).mean()
    trend_strength = 0.0
    if not np.isnan(rolling_mean.iloc[-1]):
        trend_strength = float((close.iloc[-1] - rolling_mean.iloc[-1]) / close.iloc[-1])
    volatility = _rolling_std(close, window=ma_window // 2)
    volume_ratio = _volume_ratio(volume)

    components = ScoreComponents(
        momentum=momentum,
        trend_strength=trend_strength,
        volatility=volatility,
        volume_ratio=volume_ratio,
    )

    score = 50
    score += int(np.clip(momentum * 4200, -35, 45))
    score += int(np.clip(trend_strength * 3000, -25, 25))
    score += int(np.clip((volatility or 0.0) * 900, 0, 20))
    score += int(np.clip((volume_ratio - 1.0) * 18, -10, 20))

    bounded_score = max(0, min(99, score))
    return bounded_score, components


def determine_grade(score: int) -> str:
    """Map a numerical score to a qualitative grade."""

    if score >= 85:
        return "강력"
    if score >= 60:
        return "추천"
    return "관심"


__all__ = ["ScoreComponents", "calculate_score", "determine_grade"]
