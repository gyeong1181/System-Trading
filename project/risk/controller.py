"""Drawdown guard and position sizing helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from project.risk.allocator import RiskRecommendation


@dataclass
class _RiskState:
    day: str
    week: str
    daily_loss: float
    weekly_loss: float

    @classmethod
    def blank(cls, when: datetime) -> "_RiskState":
        iso_day = when.date().isoformat()
        iso_week = f"{when.isocalendar().year}-W{when.isocalendar().week:02d}"
        return cls(day=iso_day, week=iso_week, daily_loss=0.0, weekly_loss=0.0)

    def reset_if_needed(self, when: datetime) -> None:
        iso_day = when.date().isoformat()
        iso_week = f"{when.isocalendar().year}-W{when.isocalendar().week:02d}"
        if iso_day != self.day:
            self.day = iso_day
            self.daily_loss = 0.0
        if iso_week != self.week:
            self.week = iso_week
            self.weekly_loss = 0.0


class RiskController:
    """Enforces daily/weekly loss caps for the automated engine."""

    def __init__(self, path: Path, *, daily_limit: float, weekly_limit: float) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._daily_limit = self._normalise_pct(daily_limit)
        self._weekly_limit = self._normalise_pct(weekly_limit)
        self._state = self._load_state()

    def _load_state(self) -> _RiskState:
        if self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                when = datetime.now(timezone.utc)
                state = _RiskState(**payload)
                state.reset_if_needed(when)
                state.daily_loss = self._normalise_pct(state.daily_loss)
                state.weekly_loss = self._normalise_pct(state.weekly_loss)
                return state
            except Exception:
                pass
        return _RiskState.blank(datetime.now(timezone.utc))

    def can_execute(self, recommendation: RiskRecommendation) -> bool:
        now = datetime.now(timezone.utc)
        self._state.reset_if_needed(now)
        projected_loss = self._normalise_pct(float(recommendation.bet_pct or 0.0))
        if self._state.daily_loss + projected_loss > self._daily_limit:
            return False
        if self._state.weekly_loss + projected_loss > self._weekly_limit:
            return False
        return True

    def reserve(self, recommendation: RiskRecommendation) -> None:
        now = datetime.now(timezone.utc)
        self._state.reset_if_needed(now)
        projected_loss = self._normalise_pct(float(recommendation.bet_pct or 0.0))
        self._state.daily_loss += projected_loss
        self._state.weekly_loss += projected_loss

    def persist(self) -> None:
        self._path.write_text(json.dumps(asdict(self._state)), encoding="utf-8")

    @staticmethod
    def _normalise_pct(value: float) -> float:
        """Normalise percentage inputs (expects values expressed in percent)."""

        if value <= 0:
            return 0.0
        return value / 100.0


__all__ = ["RiskController"]
