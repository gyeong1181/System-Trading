"""Utilities to remove duplicate signals and flag optimal ones."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque, Dict, Iterable, List

from project.signals.models import Signal


@dataclass
class _SignatureRecord:
    timestamp: datetime
    signature: str
    count: int


class SignalDeduplicator:
    """Track recent signals to filter duplicates and count repetitions."""

    def __init__(self, *, duplicate_window: timedelta, direction_window: timedelta) -> None:
        self._duplicate_window = duplicate_window
        self._direction_window = direction_window
        self._signature_history: Dict[str, _SignatureRecord] = {}
        self._direction_history: Dict[str, Deque[datetime]] = defaultdict(deque)

    def apply(self, signals: Iterable[Signal], now: datetime) -> None:
        for signal in signals:
            signature_key = f"{signal.symbol}|{signal.timeframe}"
            signature_value = signal.signature()
            record = self._signature_history.get(signature_key)

            if record and record.signature == signature_value and now - record.timestamp <= self._duplicate_window:
                signal.is_duplicate = True
                signal.signature_hits = record.count + 1
            else:
                signal.signature_hits = 1

            self._signature_history[signature_key] = _SignatureRecord(
                timestamp=now,
                signature=signature_value,
                count=signal.signature_hits,
            )

            direction_key = f"{signal.symbol}|{signal.timeframe}|{signal.direction.lower()}"
            history = self._direction_history[direction_key]
            while history and now - history[0] > self._direction_window:
                history.popleft()
            history.append(now)
            signal.direction_hits = len(history)

    def prune(self, now: datetime) -> None:
        stale_signatures = [
            key
            for key, record in self._signature_history.items()
            if now - record.timestamp > self._duplicate_window * 2
        ]
        for key in stale_signatures:
            self._signature_history.pop(key, None)

        for key, history in list(self._direction_history.items()):
            while history and now - history[0] > self._direction_window * 2:
                history.popleft()
            if not history:
                self._direction_history.pop(key, None)


def mark_optimal_signals(signals: Iterable[Signal]) -> None:
    grouped: Dict[str, List[Signal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.timeframe].append(signal)

    for timeframe, bucket in grouped.items():
        if not bucket:
            continue
        best_score = max(signal.score for signal in bucket)
        for signal in bucket:
            signal.is_optimal = signal.score == best_score


__all__ = ["SignalDeduplicator", "mark_optimal_signals"]
