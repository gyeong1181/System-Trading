"""Risk management utilities for position sizing and guard-rails."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class RiskManager:
    account_balance: float
    risk_per_trade_pct: float = 0.01
    min_rr: float = 1.8
    daily_loss_limit_pct: float = 0.02

    def max_trade_risk(self) -> float:
        return self.account_balance * self.risk_per_trade_pct

    def calculate_position_size(self, entry: float, stop: float) -> float:
        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0:
            return 0.0
        qty = self.max_trade_risk() / risk_per_unit
        return max(qty, 0.0)

    def validate_risk_reward(self, entry: float, stop: float, target: float) -> Tuple[bool, float]:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk == 0:
            return False, 0.0
        rr = reward / risk
        return rr >= self.min_rr, rr

    def daily_drawdown_ok(self, realized_losses: float) -> bool:
        return realized_losses <= self.account_balance * self.daily_loss_limit_pct

    def build_trade_plan(self, entry: float, stop: float, target: float, realized_losses: float = 0.0) -> Dict[str, float]:
        size = self.calculate_position_size(entry, stop)
        rr_ok, rr = self.validate_risk_reward(entry, stop, target)
        drawdown_ok = self.daily_drawdown_ok(realized_losses)
        return {
            "position_size": size,
            "risk_reward": rr,
            "risk_reward_ok": rr_ok,
            "daily_drawdown_ok": drawdown_ok,
            "max_risk_amount": self.max_trade_risk(),
        }


__all__ = ["RiskManager"]
