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
        base_leverage = self._config.base_leverage
        atr_pct = float(signal.metadata.get("atr_pct", 0.01) or 0.01)

        volatility_penalty = 1.0
        if atr_pct > 0.05:
            volatility_penalty = 0.5
        elif atr_pct > 0.025:
            volatility_penalty = 0.7
        elif atr_pct > 0.015:
            volatility_penalty = 0.85

        leverage_multiplier = {
            "strong": 1.4,
            "high": 1.1,
            "opportunity": 0.85,
            "observe": 0.6,
        }.get(grade, 0.6)
        leverage = min(
            self._config.max_leverage,
            base_leverage * leverage_multiplier * max(0.6, volatility_penalty * 1.1),
        )

        confidence_weight = {
            "strong": 1.0,
            "high": 0.75,
            "opportunity": 0.5,
            "observe": 0.3,
        }.get(grade, 0.3)
        max_bet = self._config.bet_size_pct
        min_bet = self._config.min_bet_pct
        target_bet = min_bet + (max_bet - min_bet) * confidence_weight
        bet_pct = round(max(min_bet, min(max_bet, target_bet * volatility_penalty)), 2)

        risk_reward = float(signal.metadata.get("risk_reward", self._config.risk_reward))
        if signal.direction.lower() == "short":
            risk_reward = round(risk_reward * 0.95, 2)

        return RiskRecommendation(
            leverage=round(leverage, 2),
            bet_pct=round(bet_pct, 2),
            risk_reward=round(risk_reward, 2),
        )


__all__ = ["RiskAdvisor", "RiskRecommendation"]
