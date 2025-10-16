"""Outcome tracking helpers for post-trade analytics."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from project.data.binance_client import fetch_latest_price
from project.data.signal_repository import SignalRepository

LOGGER = logging.getLogger(__name__)


class OutcomeTracker:
    """Schedules and records post-alert performance checks."""

    def __init__(
        self,
        repository: SignalRepository,
        *,
        ttl_hours: int = 6,
        symbols: dict[str, str],
    ) -> None:
        self._repository = repository
        self._ttl = timedelta(hours=ttl_hours)
        self._symbols = {alias.upper(): market for alias, market in symbols.items()}

    def schedule(self, signal_id: str, created_at: datetime) -> None:
        when = created_at + self._ttl
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        self._repository.schedule_outcome(signal_id, when)

    def process_due_jobs(self, client) -> None:
        now = datetime.now(timezone.utc)
        jobs = self._repository.fetch_due_jobs(now)
        for job in jobs:
            try:
                self._evaluate_job(job, client, now)
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.exception("Failed to evaluate outcome for %s: %s", job.get("signal_id"), exc)

    def _evaluate_job(self, job: dict, client, now: datetime) -> None:
        signal_id = job["signal_id"]
        symbol_alias = str(job.get("symbol", "")).upper()
        market = self._symbols.get(symbol_alias, job.get("metadata", {}).get("market", symbol_alias))
        price = fetch_latest_price(market, client=client)

        created_at = self._parse_datetime(job["created_at"])
        target = self._coerce_float(job.get("target_price"))
        stop = self._coerce_float(job.get("stop_price"))
        entry = self._coerce_float(job.get("entry_price"))
        direction = str(job.get("direction", "")).lower()

        pnl = 0.0
        outcome = "open"
        notes = f"price={price:.2f}, entry={entry}, target={target}, stop={stop}"

        if direction == "long":
            pnl = (price - entry) / entry if entry else 0.0
            if target and price >= target:
                outcome = "target_hit"
            elif stop and price <= stop:
                outcome = "stop_hit"
        elif direction == "short":
            pnl = (entry - price) / entry if entry else 0.0
            if target and price <= target:
                outcome = "target_hit"
            elif stop and price >= stop:
                outcome = "stop_hit"

        if outcome == "open":
            if now - created_at <= timedelta(hours=24):
                reschedule_for = now + self._ttl
                LOGGER.debug("Rescheduling outcome check for %s at %s", signal_id, reschedule_for.isoformat())
                self._repository.schedule_outcome(signal_id, reschedule_for)
                return
            outcome = "stale"

        LOGGER.info("Recording outcome %s for %s (pnl %.4f)", outcome, signal_id, pnl)
        self._repository.record_outcome(
            signal_id=signal_id,
            pnl=round(pnl, 4),
            outcome=outcome,
            notes=notes,
            resolved_at=now,
        )

    @staticmethod
    def _coerce_float(value) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

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


__all__ = ["OutcomeTracker"]
