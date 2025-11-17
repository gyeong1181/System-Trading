"""Helpers to load external metrics that enrich the scoring engine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import json

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore


@dataclass(frozen=True)
class ExternalMetrics:
    """Container for the non-price metrics powering the composite score."""

    exchange_inflow_index: float = 0.5
    exchange_outflow_index: float = 0.5
    whale_activity_index: float = 0.5
    mvrv_zscore: float = 0.0
    funding_rate: float = 0.0
    open_interest_change: float = 0.0
    options_skew: float = 0.0
    max_pain_distance: float = 0.0
    fear_greed: float = 50.0
    google_trends: float = 50.0
    volume_sentiment: float = 0.5
    dxy_trend: float = 0.0
    rates_trend: float = 0.0
    sp500_trend: float = 0.0
    vix_level: float = 0.0
    social_sentiment: float = 0.0
    twitter_sentiment: float = 0.0
    reddit_sentiment: float = 0.0
    telegram_sentiment: float = 0.0
    pro_trader_bias: float = 0.0
    orderbook_heatmap: float = 0.5

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "ExternalMetrics":
        defaults = cls()
        return cls(
            **{
                field: float(payload.get(field, getattr(defaults, field)))
                for field in cls.__dataclass_fields__
            }
        )  # type: ignore[attr-defined]


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse YAML external metric files.")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_external_metrics(path: Path | None = None) -> ExternalMetrics:
    """Load external metrics from JSON/YAML if present, otherwise return neutral values."""

    candidates = []
    if path is not None:
        candidates.append(path)
    else:
        candidates.extend(
            [
                Path("external_metrics.yaml"),
                Path("external_metrics.yml"),
                Path("external_metrics.json"),
            ]
        )

    for candidate in candidates:
        if not candidate.exists():
            continue
        data: Dict[str, Any]
        if candidate.suffix.lower() in {".yaml", ".yml"}:
            data = _load_yaml(candidate)
        else:
            data = _load_json(candidate)
        if not isinstance(data, dict):
            continue
        return ExternalMetrics.from_mapping(data)

    return ExternalMetrics()


__all__ = ["ExternalMetrics", "load_external_metrics"]
