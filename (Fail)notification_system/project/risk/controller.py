"""Drawdown guard and position sizing helpers with reservation tracking."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from project.risk.allocator import RiskRecommendation


@dataclass
class _RiskState:
    day: str
    week: str
    daily_loss: float
    weekly_loss: float
    reservations: Dict[str, Dict[str, float | str]] = field(default_factory=dict)

    @classmethod
    def blank(cls, when: datetime) -> "_RiskState":
        iso_day = when.date().isoformat()
        iso_week = f"{when.isocalendar().year}-W{when.isocalendar().week:02d}"
        return cls(day=iso_day, week=iso_week, daily_loss=0.0, weekly_loss=0.0, reservations={})

    def reset_if_needed(self, when: datetime) -> None:
        iso_day = when.date().isoformat()
        iso_week = f"{when.isocalendar().year}-W{when.isocalendar().week:02d}"
        if iso_day != self.day:
            self.day = iso_day
            self.daily_loss = 0.0
            self.reservations.clear()
        if iso_week != self.week:
            self.week = iso_week
            self.weekly_loss = 0.0


class RiskController:
    """Enforces daily/weekly loss caps for the automated engine."""

    def __init__(
        self,
        path: Path,
        *,
        daily_limit: float,
        weekly_limit: float,
        reservation_ttl_hours: float = 2.0,
        limits_enabled: bool = True,
    ) -> None:
        self._limits_enabled = limits_enabled
        self._path = path
        self._daily_limit = self._normalise_pct(daily_limit)
        self._weekly_limit = self._normalise_pct(weekly_limit)
        self._reservation_ttl = timedelta(hours=reservation_ttl_hours)
        if self._limits_enabled:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._state = self._load_state()
        else:
            self._state = _RiskState.blank(datetime.now(timezone.utc))

    def _load_state(self) -> _RiskState:
        if self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                when = datetime.now(timezone.utc)
                reservations = {
                    str(k): {
                        "amount": self._normalise_pct(float(v.get("amount", 0.0))),
                        "created_at": v.get("created_at"),
                    }
                    for k, v in payload.get("reservations", {}).items()
                }
                state = _RiskState(
                    day=payload.get("day", when.date().isoformat()),
                    week=payload.get("week", f"{when.isocalendar().year}-W{when.isocalendar().week:02d}"),
                    daily_loss=self._normalise_pct(float(payload.get("daily_loss", 0.0))),
                    weekly_loss=self._normalise_pct(float(payload.get("weekly_loss", 0.0))),
                    reservations=reservations,
                )
                state.reset_if_needed(when)
                return state
            except Exception:
                pass
        return _RiskState.blank(datetime.now(timezone.utc))

    def can_execute(self, recommendation: RiskRecommendation) -> bool:
        if not self._limits_enabled:
            return True
        now = datetime.now(timezone.utc)
        self._state.reset_if_needed(now)
        self._prune_reservations(now)
        projected_loss = self._normalise_pct(float(recommendation.bet_pct or 0.0))
        if self._state.daily_loss + projected_loss > self._daily_limit:
            return False
        if self._state.weekly_loss + projected_loss > self._weekly_limit:
            return False
        return True

    def reserve(self, signal_id: str, recommendation: RiskRecommendation) -> None:
        if not self._limits_enabled:
            return
        now = datetime.now(timezone.utc)
        self._state.reset_if_needed(now)
        self._prune_reservations(now)
        projected_loss = self._normalise_pct(float(recommendation.bet_pct or 0.0))
        self._state.daily_loss += projected_loss
        self._state.weekly_loss += projected_loss
        self._state.reservations[str(signal_id)] = {
            "amount": projected_loss,
            "created_at": now.isoformat(),
        }
        self.persist()

    def release(self, signal_id: str, realized_pnl: float) -> None:
        if not self._limits_enabled:
            return
        now = datetime.now(timezone.utc)
        self._state.reset_if_needed(now)
        reservation = self._state.reservations.pop(str(signal_id), None)
        if reservation:
            amount = float(reservation.get("amount", 0.0))
            self._state.daily_loss = max(0.0, self._state.daily_loss - amount)
            self._state.weekly_loss = max(0.0, self._state.weekly_loss - amount)
        if realized_pnl < 0:
            loss_fraction = abs(realized_pnl)
            loss_pct = self._normalise_pct(loss_fraction * 100 if loss_fraction <= 1 else loss_fraction)
            self._state.daily_loss += loss_pct
            self._state.weekly_loss += loss_pct
        self.persist()

    def persist(self) -> None:
        if not self._limits_enabled:
            return
        payload = {
            "day": self._state.day,
            "week": self._state.week,
            "daily_loss": self._state.daily_loss * 100,
            "weekly_loss": self._state.weekly_loss * 100,
            "reservations": {
                key: {
                    "amount": value["amount"] * 100,
                    "created_at": value["created_at"],
                }
                for key, value in self._state.reservations.items()
            },
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _prune_reservations(self, now: datetime) -> None:
        if not self._limits_enabled:
            return
        expired = []
        for signal_id, data in self._state.reservations.items():
            created_at = self._parse_datetime(data.get("created_at"))
            if now - created_at >= self._reservation_ttl:
                amount = float(data.get("amount", 0.0))
                self._state.daily_loss = max(0.0, self._state.daily_loss - amount)
                self._state.weekly_loss = max(0.0, self._state.weekly_loss - amount)
                expired.append(signal_id)
        for signal_id in expired:
            self._state.reservations.pop(signal_id, None)
        if expired:
            self.persist()

    @staticmethod
    def _parse_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                return datetime.now(timezone.utc)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalise_pct(value: float) -> float:
        if value <= 0:
            return 0.0
        if value > 1:
            return value / 100.0
        return value


__all__ = ["RiskController"]
