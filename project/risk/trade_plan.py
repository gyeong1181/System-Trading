"""Construct actionable trade plans from signal metadata and risk settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from project.risk.allocator import RiskRecommendation
from project.signals.models import Signal


@dataclass(frozen=True)
class TradePlan:
    entry: float
    target: float
    stop: float
    leverage: float
    bet_pct: float
    risk_reward: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "entry": self.entry,
            "target": self.target,
            "stop": self.stop,
            "leverage": self.leverage,
            "bet_pct": self.bet_pct,
            "risk_reward": self.risk_reward,
        }


class TradePlanBuilder:
    """Estimate entry/target/stop levels using ATR heuristics."""

    def __init__(self, *, atr_multiplier: float = 1.0) -> None:
        self._atr_multiplier = atr_multiplier

    def build(self, signal: Signal, recommendation: RiskRecommendation) -> TradePlan:
        atr = float(signal.metadata.get("atr", 0.0)) * self._atr_multiplier
        close = float(signal.metadata.get("close", 0.0))
        risk_reward = float(signal.metadata.get("risk_reward", recommendation.risk_reward))
        if close <= 0 or atr <= 0:
            entry = close or 0.0
            target = close
            stop = close
        else:
            if signal.direction.lower() == "long":
                entry = close
                stop = max(0.0, close - atr)
                target = close + atr * risk_reward
            else:
                entry = close
                stop = close + atr
                target = max(0.0, close - atr * risk_reward)
        return TradePlan(
            entry=round(entry, 2),
            target=round(target, 2),
            stop=round(stop, 2),
            leverage=recommendation.leverage,
            bet_pct=recommendation.bet_pct,
            risk_reward=recommendation.risk_reward,
        )


__all__ = ["TradePlan", "TradePlanBuilder"]
