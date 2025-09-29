"""Signal consensus and de-duplication utilities."""

from .filter import SignalDeduplicator, mark_optimal_signals

__all__ = ["SignalDeduplicator", "mark_optimal_signals"]
