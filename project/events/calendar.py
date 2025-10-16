"""Event calendar utilities for blackout-aware trading."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import json

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore


@dataclass(frozen=True)
class ScheduledEvent:
    """Represents a market-moving event window."""

    name: str
    start: datetime
    end: datetime
    symbols: Optional[Sequence[str]] = None

    def is_active(self, when: datetime, symbol: Optional[str] = None) -> bool:
        if when < self.start or when > self.end:
            return False
        if symbol is None or not self.symbols:
            return True
        return symbol.upper() in {s.upper() for s in self.symbols}


class EventCalendar:
    """Holds blackout windows loaded from configuration files."""

    def __init__(self, events: Iterable[ScheduledEvent] | None = None) -> None:
        self._events: List[ScheduledEvent] = list(events or [])

    def is_blackout(self, when: datetime, symbol: Optional[str] = None) -> bool:
        check_time = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        return any(event.is_active(check_time, symbol) for event in self._events)

    def upcoming(self, when: datetime) -> List[ScheduledEvent]:
        check_time = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        return [event for event in self._events if event.end >= check_time]

    @classmethod
    def from_file(cls, path: Path | None) -> "EventCalendar":
        if path is None or not path.exists():
            return cls()
        payload = _load_payload(path)
        events = [_parse_event(item) for item in payload if isinstance(item, dict)]
        return cls(event for event in events if event is not None)


def _load_payload(path: Path) -> List[dict]:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML event calendars.")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    else:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    if isinstance(data, dict):
        values = data.get("events", [])
    else:
        values = data
    return list(values or [])


def _parse_event(item: dict) -> ScheduledEvent | None:
    try:
        name = str(item["name"])
        start = _parse_datetime(item["start"])
        end = _parse_datetime(item.get("end") or item["start"])
        symbols = item.get("symbols")
    except Exception:
        return None
    if end < start:
        end = start
    return ScheduledEvent(name=name, start=start, end=end, symbols=symbols)


def _parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


__all__ = ["ScheduledEvent", "EventCalendar"]
