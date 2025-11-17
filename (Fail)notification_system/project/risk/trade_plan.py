"""Construct actionable trade plans from signal metadata and risk settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from project.risk.allocator import RiskRecommendation
from project.signals.models import Signal


@dataclass(frozen=True)
class TradeLeg:
    label: str
    price: float
    size_pct: float
    status: str = "pending"
    enabled: bool = True

    def as_dict(self) -> Dict[str, float | str | bool]:
        return {
            "label": self.label,
            "price": round(self.price, 2),
            "size_pct": round(self.size_pct, 4),
            "status": self.status,
            "enabled": bool(self.enabled),
        }


@dataclass(frozen=True)
class TradePlan:
    entry: float
    target: float
    stop: float
    leverage: float
    bet_pct: float
    risk_reward: float
    exit_legs: List[TradeLeg] = field(default_factory=list)
    entry_legs: List[TradeLeg] = field(default_factory=list)
    partials_exit_enabled: bool = False
    partials_entry_enabled: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {
            "entry": round(self.entry, 2),
            "target": round(self.target, 2),
            "stop": round(self.stop, 2),
            "leverage": self.leverage,
            "bet_pct": self.bet_pct,
            "risk_reward": self.risk_reward,
            "exit_legs": [leg.as_dict() for leg in self.exit_legs],
            "entry_legs": [leg.as_dict() for leg in self.entry_legs],
            "partials_exit_enabled": self.partials_exit_enabled,
            "partials_entry_enabled": self.partials_entry_enabled,
        }


class TradePlanBuilder:
    """Estimate entry/target/stop levels using ATR heuristics with partials."""

    def __init__(
        self,
        *,
        atr_multiplier: float = 1.0,
        exit_percents: tuple[float, float, float] = (0.5, 0.3, 0.2),
        exit_levels: tuple[float, float, float] = (0.45, 0.75, 1.0),
        entry_offsets: tuple[float, float, float] = (0.0, -0.005, -0.01),
        entry_percents: tuple[float, float, float] = (0.6, 0.3, 0.1),
        exit_min_rr: float = 1.6,
        exit_min_atr_pct: float = 0.015,
        entry_min_atr_pct: float = 0.02,
    ) -> None:
        self._atr_multiplier = atr_multiplier
        self._exit_percents = exit_percents
        self._exit_levels = exit_levels
        self._entry_offsets = entry_offsets
        self._entry_percents = entry_percents
        self._exit_min_rr = exit_min_rr
        self._exit_min_atr_pct = exit_min_atr_pct
        self._entry_min_atr_pct = entry_min_atr_pct

    def build(self, signal: Signal, recommendation: RiskRecommendation) -> TradePlan:
        atr = max(0.0, float(signal.metadata.get("atr", 0.0))) * self._atr_multiplier
        close = float(signal.metadata.get("close", 0.0))
        risk_reward = float(signal.metadata.get("risk_reward", recommendation.risk_reward))
        atr_pct = float(signal.metadata.get("atr_pct", 0.0))
        if atr_pct <= 0 and close > 0 and atr > 0:
            atr_pct = atr / close

        direction = signal.direction.lower()
        entry = close or 0.0
        target = entry
        stop = entry

        if entry > 0 and atr > 0:
            move = atr * max(0.8, risk_reward)
            if direction == "long":
                target = entry + move
                stop = max(0.0, entry - atr)
            else:
                target = max(0.0, entry - move)
                stop = entry + atr

        enable_partial_exit = (
            risk_reward >= self._exit_min_rr and atr_pct >= self._exit_min_atr_pct
        )
        enable_partial_entry = atr_pct >= self._entry_min_atr_pct

        exit_legs = self._build_exit_legs(direction, entry, target, enable_partial_exit)
        entry_legs = self._build_entry_legs(direction, entry, enable_partial_entry)

        return TradePlan(
            entry=entry,
            target=target,
            stop=stop,
            leverage=recommendation.leverage,
            bet_pct=recommendation.bet_pct,
            risk_reward=recommendation.risk_reward,
            exit_legs=exit_legs,
            entry_legs=entry_legs,
            partials_exit_enabled=enable_partial_exit,
            partials_entry_enabled=enable_partial_entry,
        )

    def _build_exit_legs(
        self,
        direction: str,
        entry: float,
        target: float,
        enable_partial: bool,
    ) -> List[TradeLeg]:
        legs: List[TradeLeg] = []
        if entry <= 0 or target <= 0 or entry == target:
            legs.append(TradeLeg(label="Full Exit", price=target, size_pct=1.0))
            return legs

        move = abs(target - entry)
        if move <= 0:
            return [TradeLeg(label="Full Exit", price=target, size_pct=1.0)]
        if not enable_partial:
            return [TradeLeg(label="Full Exit", price=target, size_pct=1.0)]

        for idx, (portion, level) in enumerate(zip(self._exit_percents, self._exit_levels), start=1):
            if portion <= 0:
                continue
            if direction == "long":
                price = entry + move * level
            else:
                price = entry - move * level
            legs.append(
                TradeLeg(
                    label=f"TP{idx}",
                    price=price,
                    size_pct=portion,
                )
            )
        return legs

    def _build_entry_legs(self, direction: str, entry: float, enable_partial: bool) -> List[TradeLeg]:
        legs: List[TradeLeg] = []
        if entry <= 0:
            return legs

        for idx, offset in enumerate(self._entry_offsets):
            if idx == 0:
                portion = 1.0 if not enable_partial else self._entry_percents[0]
                legs.append(
                    TradeLeg(
                        label="Entry1",
                        price=entry,
                        size_pct=portion,
                        enabled=True,
                    )
                )
                continue

            if not enable_partial:
                break

            if direction == "long":
                price = entry * (1 + offset)
            else:
                price = entry * (1 - offset)
            portion = self._entry_percents[idx] if idx < len(self._entry_percents) else 0.0
            enabled = portion > 0
            legs.append(
                TradeLeg(
                    label=f"Entry{idx+1}",
                    price=round(price, 2),
                    size_pct=portion,
                    enabled=enabled,
                )
            )
        return legs


__all__ = ["TradePlan", "TradePlanBuilder", "TradeLeg"]
