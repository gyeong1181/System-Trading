"""Rolling score tracker used to compute delta thresholds."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Dict, Tuple
from collections import deque
import json


@dataclass(frozen=True)
class ScoreSnapshot:
    """Computed score context for a symbol/timeframe."""

    symbol: str
    timeframe: str
    score: int
    delta: float
    rolling_avg: float
    window_size: int


class ScoreTracker:
    """Maintains sliding score windows to evaluate Δ thresholds."""

    def __init__(self, path: Path, *, window: timedelta = timedelta(minutes=30)) -> None:
        self._path = path
        self._window = window
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._history: Dict[str, Deque[Tuple[datetime, int]]] = {}
        self._load()

    def _key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol.upper()}|{timeframe}"

    def update(self, *, symbol: str, timeframe: str, score: int, when: datetime) -> ScoreSnapshot:
        key = self._key(symbol, timeframe)
        history = self._history.setdefault(key, deque())
        timestamp = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        cutoff = timestamp - self._window
        while history and history[0][0] < cutoff:
            history.popleft()
        history.append((timestamp, int(score)))
        rolling_avg = sum(value for _, value in history) / max(1, len(history))
        delta = score - rolling_avg
        snapshot = ScoreSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            score=int(score),
            delta=float(round(delta, 2)),
            rolling_avg=float(round(rolling_avg, 2)),
            window_size=len(history),
        )
        self._persist()
        return snapshot

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        now = datetime.now(timezone.utc)
        for key, items in raw.items():
            buffer: Deque[Tuple[datetime, int]] = deque()
            for entry in items:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if now - ts <= self._window:
                    buffer.append((ts, int(entry["score"])))
            if buffer:
                self._history[key] = buffer

    def _persist(self) -> None:
        payload: Dict[str, list] = {}
        for key, entries in self._history.items():
            payload[key] = [
                {"timestamp": ts.isoformat(), "score": score}
                for ts, score in entries
            ]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["ScoreTracker", "ScoreSnapshot"]
