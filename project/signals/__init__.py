"""Signal module exports for the swing alert MVP."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SignalResult:
    """Unified return container for indicator modules."""

    name: str
    score: float
    summary: str
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SignalResult"]
