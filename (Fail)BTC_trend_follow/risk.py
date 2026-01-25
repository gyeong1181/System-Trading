from dataclasses import dataclass
from typing import Tuple


@dataclass
class RiskConfig:
    risk_pct: float = 1.0
    atr_stop_multiple: float = 2.2
    tp1_multiple: float = 2.5
    runner_multiple: float = 4.0
    trail_multiple: float = 2.5
    min_qty: float = 0.001
    leverage: float = 1.0


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def position_size(self, equity: float, atr_value: float) -> Tuple[float, float]:
        atr_stop = atr_value * self.config.atr_stop_multiple
        base_stop_dist = atr_stop
        risk_capital = equity * (self.config.risk_pct / 100)
        if base_stop_dist <= 0:
            return self.config.min_qty, atr_stop
        effective_risk = risk_capital * max(self.config.leverage, 0.01)
        qty = max(effective_risk / base_stop_dist, self.config.min_qty)
        return qty, atr_stop

    def take_profit_targets(self, atr_stop: float) -> Tuple[float, float]:
        tp1 = atr_stop * self.config.tp1_multiple
        runner = atr_stop * self.config.runner_multiple
        return tp1, runner

    def trail_offset(self, atr_value: float) -> float:
        return atr_value * self.config.trail_multiple
