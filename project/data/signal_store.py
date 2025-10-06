"""Persistent storage for generated trading signals."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from project.signals.models import Signal


class SignalStore:
    """Append-only CSV store for signal logs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_header()

    def _write_header(self) -> None:
        header = [
            "timestamp",
            "symbol",
            "timeframe",
            "direction",
            "score",
            "grade",
            "conditions",
            "risk_reward",
            "leverage",
            "bet_pct",
            "summary",
        ]
        with self._path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)

    def append(self, signals: Iterable[Signal], as_of: datetime) -> None:
        if not signals:
            return
        with self._path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            for signal in signals:
                risk = signal.metadata.get("risk_recommendation") or {}
                summary = signal.metadata.get("summary", [])
                conditions = signal.metadata.get("conditions", [])
                writer.writerow(
                    [
                        signal.timestamp.isoformat(),
                        signal.symbol,
                        signal.timeframe,
                        signal.direction,
                        signal.score,
                        signal.grade,
                        "|".join(str(item) for item in conditions),
                        signal.metadata.get("risk_reward", risk.get("risk_reward")),
                        risk.get("leverage"),
                        risk.get("bet_pct"),
                        " | ".join(str(item) for item in summary),
                    ]
                )


__all__ = ["SignalStore"]
