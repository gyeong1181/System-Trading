"""Outcome tracking helpers for post-trade analytics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from project.data.signal_repository import SignalRepository


class OutcomeTracker:
    """Schedules and records post-alert performance checks."""

    def __init__(self, repository: SignalRepository, *, ttl_hours: int = 6) -> None:
        self._repository = repository
        self._ttl = timedelta(hours=ttl_hours)

    def schedule(self, signal_id: str, created_at: datetime) -> None:
        when = created_at + self._ttl
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        self._repository.schedule_outcome(signal_id, when)

    def tag_outcome(
        self,
        *,
        signal_id: str,
        pnl: float,
        outcome: str,
        notes: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> None:
        self._repository.record_outcome(
            signal_id=signal_id,
            pnl=pnl,
            outcome=outcome,
            notes=notes,
            resolved_at=resolved_at,
        )


__all__ = ["OutcomeTracker"]
