"""Translate signal strength into actionable risk parameters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from project.configuration import RiskConfig
from project.signals.models import Signal


@dataclass(frozen=True)
class RiskRecommendation:
    leverage: float
    bet_pct: float
    risk_reward: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "leverage": self.leverage,
            "bet_pct": self.bet_pct,
            "risk_reward": self.risk_reward,
        }


class RiskAdvisor:
    """Apply grade-sensitive tweaks to the base risk configuration."""

    def __init__(self, config: RiskConfig) -> None:
        self._config = config

    def recommend(self, signal: Signal) -> RiskRecommendation:
        grade = signal.grade
        base_lev = self._config.base_leverage
        leverage_multiplier = {
            "강력": 1.4,
            "추천": 1.0,
            "관심": 0.7,
        }.get(grade, 1.0)
        leverage = min(self._config.max_leverage, base_lev * leverage_multiplier)

        bet_multiplier = {
            "강력": 1.3,
            "추천": 1.0,
            "관심": 0.7,
        }.get(grade, 1.0)
        bet_pct = max(0.5, self._config.bet_size_pct * bet_multiplier)
        risk_reward = self._config.risk_reward
        if signal.direction.lower() == "short":
            risk_reward = round(risk_reward * 0.95, 2)

        return RiskRecommendation(
            leverage=round(leverage, 2),
            bet_pct=round(bet_pct, 2),
            risk_reward=round(risk_reward, 2),
        )


__all__ = ["RiskAdvisor", "RiskRecommendation"]
