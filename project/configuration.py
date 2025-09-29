"""Configuration helpers for the automated signal system."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import logging
import os

try:
    import yaml
except ImportError:  # pragma: no cover - handled at runtime
    yaml = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime knobs for the signal engine."""

    timeframes: List[str]
    data_limit: int
    duplicate_window_minutes: int
    direction_window_minutes: int
    min_score: int


@dataclass(frozen=True)
class RiskConfig:
    """Risk recommendation settings."""

    base_leverage: float
    max_leverage: float
    bet_size_pct: float
    risk_reward: float


@dataclass(frozen=True)
class AlertsConfig:
    """Alert channel settings."""

    telegram_token: Optional[str]
    telegram_chat_id: Optional[str]
    parse_mode: Optional[str]
    disable_notification: bool
    log_path: Path


@dataclass(frozen=True)
class Settings:
    """Top-level configuration used by the orchestrator."""

    symbols: Dict[str, str]
    runtime: RuntimeConfig
    risk: RiskConfig
    alerts: AlertsConfig


def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned = value.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]
        env[key.strip()] = cleaned
    return env


def _load_yaml_config(path: Path) -> Dict[str, object]:
    if not path.exists():
        LOGGER.info("Configuration file %s not found; using defaults.", path)
        return {}

    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to load configuration files. Install it with 'pip install pyyaml'."
        )

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)  # type: ignore[arg-type]
    return data or {}


def _parse_timeframes(source: object) -> List[str]:
    if not source:
        return []

    if isinstance(source, str):
        parts = [part.strip() for part in source.split(",")]
    elif isinstance(source, Iterable):
        parts = [str(part).strip() for part in source]
    else:
        return []
    return [p for p in parts if p]


def _ensure_timeframes(config: Dict[str, object], env_map: Dict[str, str]) -> List[str]:
    candidates: List[str] = []
    env_value = os.getenv("TRADING_TIMEFRAMES") or env_map.get("TRADING_TIMEFRAMES")
    if env_value:
        candidates = _parse_timeframes(env_value)

    if not candidates:
        candidates = _parse_timeframes(config.get("timeframes"))

    if not candidates:
        single = config.get("timeframe")
        if isinstance(single, str) and single:
            candidates = [single]

    if not candidates:
        candidates = ["1h"]

    return candidates


def _resolve_symbols(raw_config: Dict[str, object]) -> Dict[str, str]:
    symbols = raw_config.get("symbols")
    if isinstance(symbols, dict):
        resolved = {str(alias).upper(): str(market) for alias, market in symbols.items()}
        return resolved
    return {"BTCUSDT": "BTC/USDT", "ETHUSDT": "ETH/USDT"}


def _get_bool(config: Dict[str, object], key: str, default: bool = False) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return default


def load_settings(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    env_path: Path = DEFAULT_ENV_PATH,
) -> Settings:
    """Load configuration values from YAML and optional .env overrides."""

    env_map = _read_env_file(env_path)
    yaml_config = _load_yaml_config(config_path)

    timeframes = _ensure_timeframes(yaml_config, env_map)
    data_limit = int(yaml_config.get("data_limit", 240))
    duplicate_window_minutes = int(yaml_config.get("duplicate_window_minutes", 120))
    direction_window_minutes = int(yaml_config.get("direction_window_minutes", 90))
    min_score = int(yaml_config.get("min_signal_score", 55))

    runtime = RuntimeConfig(
        timeframes=timeframes,
        data_limit=data_limit,
        duplicate_window_minutes=duplicate_window_minutes,
        direction_window_minutes=direction_window_minutes,
        min_score=min_score,
    )

    risk_config = yaml_config.get("risk", {})
    base_leverage = float(risk_config.get("base_leverage", yaml_config.get("leverage", 3)))
    max_leverage = float(risk_config.get("max_leverage", max(5, base_leverage)))
    bet_size_pct = float(risk_config.get("bet_size_pct", yaml_config.get("risk_per_trade", 0.05)))
    if bet_size_pct <= 1:
        bet_size_pct *= 100
    risk_reward = float(risk_config.get("risk_reward", 2.0))

    risk = RiskConfig(
        base_leverage=base_leverage,
        max_leverage=max_leverage,
        bet_size_pct=bet_size_pct,
        risk_reward=risk_reward,
    )

    alerts_config = yaml_config.get("alerts", {})
    telegram_config = alerts_config.get("telegram", {}) if isinstance(alerts_config, dict) else {}
    log_dir = Path(yaml_config.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "signal_engine.log"

    alerts = AlertsConfig(
        telegram_token=str(telegram_config.get("token")) if telegram_config.get("token") else None,
        telegram_chat_id=str(telegram_config.get("chat_id")) if telegram_config.get("chat_id") else None,
        parse_mode=str(telegram_config.get("parse_mode")) if telegram_config.get("parse_mode") else None,
        disable_notification=_get_bool(telegram_config, "disable_notification", False),
        log_path=log_path,
    )

    symbols = _resolve_symbols(yaml_config)

    return Settings(symbols=symbols, runtime=runtime, risk=risk, alerts=alerts)


__all__ = [
    "RuntimeConfig",
    "RiskConfig",
    "AlertsConfig",
    "Settings",
    "load_settings",
]
