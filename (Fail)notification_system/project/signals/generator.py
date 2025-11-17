"""Generate trading signals from market data."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pandas as pd

from project.configuration import RuntimeConfig
from project.data.context import AnalysisContext
from project.scoring import calculate_composite_score, determine_grade
from project.signals.models import Signal


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
    context: AnalysisContext,
) -> List[Signal]:
    signals: List[Signal] = []
    for symbol, df in market_data.items():
        prepared = _prepare_dataframe(df)
        if len(prepared) < 30:
            continue

        composite = calculate_composite_score(symbol, timeframe, prepared, context)
        score = composite.total
        if score < runtime.min_score:
            continue

        if len(composite.conditions) < 2:
            continue

        if composite.risk_reward < 1.5:
            continue

        direction = composite.bias
        grade = determine_grade(score)
        categories = {
            category.label: {
                "value": round(category.value, 2),
                "weight": category.weight,
                "notes": list(category.notes),
            }
            for category in composite.categories.values()
        }
        metadata = {
            "timeframe": timeframe,
            "momentum": composite.momentum,
            "trend_strength": composite.trend_strength,
            "atr": composite.atr,
            "atr_pct": composite.atr_pct,
            "risk_reward": round(composite.risk_reward, 2),
            "categories": categories,
            "conditions": list(composite.conditions),
            "summary": list(composite.summary),
            "orderbook_bias": context.heatmap_bias(),
            "close": float(prepared["close"].astype(float).iloc[-1]),
        }
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
