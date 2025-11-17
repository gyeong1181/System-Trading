"""Helper for scheduling periodic performance analyses."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class AnalysisState:
    last_run_at: datetime
    last_signal_count: int

    @classmethod
    def empty(cls) -> "AnalysisState":
        return cls(last_run_at=datetime.fromtimestamp(0, tz=timezone.utc), last_signal_count=0)

    def to_json(self) -> dict:
        return {
            "last_run_at": self.last_run_at.isoformat(),
            "last_signal_count": self.last_signal_count,
        }

    @classmethod
    def from_json(cls, payload: dict) -> "AnalysisState":
        try:
            last_run_at = datetime.fromisoformat(payload["last_run_at"])
            if last_run_at.tzinfo is None:
                last_run_at = last_run_at.replace(tzinfo=timezone.utc)
            last_signal_count = int(payload.get("last_signal_count", 0))
            return cls(last_run_at=last_run_at, last_signal_count=last_signal_count)
        except Exception:
            return cls.empty()


class PerformanceScheduler:
    """Decides when to run performance analysis based on interval and signal counts."""

    def __init__(
        self,
        *,
        state_path: Path,
        interval: timedelta,
        min_new_signals: int,
    ) -> None:
        self._state_path = state_path
        self._interval = interval
        self._min_new_signals = min_new_signals
        self._state = self._load_state()

    def _load_state(self) -> AnalysisState:
        if not self._state_path.exists():
            return AnalysisState.empty()
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return AnalysisState.from_json(payload)
        except Exception:
            return AnalysisState.empty()

    def should_run(self, *, total_signals: int, now: datetime) -> bool:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if now - self._state.last_run_at >= self._interval:
            return True
        if total_signals - self._state.last_signal_count >= self._min_new_signals:
            return True
        return False

    def mark_executed(self, *, total_signals: int, when: datetime) -> None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        self._state = AnalysisState(last_run_at=when, last_signal_count=total_signals)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._state.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
