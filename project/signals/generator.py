"""Generate trading signals from market data."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pandas as pd

from project.configuration import RuntimeConfig
from project.scoring import ScoreComponents, calculate_score, determine_grade
from project.signals.models import Signal


def _direction_from_components(timeframe: str, components: ScoreComponents) -> str | None:
    momentum = components.momentum
    trend = components.trend_strength
    tf = timeframe.lower()
    if tf in {"5m", "15m"}:
        threshold = 0.0006
    else:
        threshold = 0.0012

    if momentum > threshold and trend >= 0:
        return "long"
    if momentum < -threshold and trend <= 0:
        return "short"
    return None


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index, utc=True)
    return df.tail(240)


def generate_signals(
    market_data: Dict[str, pd.DataFrame],
    *,
    timeframe: str,
    runtime: RuntimeConfig,
    as_of: datetime,
) -> List[Signal]:
    signals: List[Signal] = []
    for symbol, df in market_data.items():
        prepared = _prepare_dataframe(df)
        if len(prepared) < 30:
            continue

        score, components = calculate_score(prepared)
        if score < runtime.min_score:
            continue

        direction = _direction_from_components(timeframe, components)
        if direction is None:
            continue

        grade = determine_grade(score)
        metadata = components.as_dict()
        metadata.update({"timeframe": timeframe})
        signal = Signal(
            symbol=symbol,
            direction=direction,
            timeframe=timeframe,
            score=score,
            grade=grade,
            timestamp=as_of,
            metadata=metadata,
        )
        signals.append(signal)

    return signals


__all__ = ["generate_signals"]
