from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib

from dotenv import load_dotenv

from src.paths import discover_repo_root, ensure_runtime_directories


@dataclass
class StrategyRuntimeConfig:
    strategy_id: str
    class_name: str
    symbols: list[str]
    timeframe: str
    priority: int
    leverage: int
    enabled: bool
    research_timeframes: list[str] = field(default_factory=list)
    demo_only: bool = False
    default_params: dict[str, float] = field(default_factory=dict)


@dataclass
class Settings:
    repo_root: Path
    database_path: Path
    state_path: Path
    market_dir: Path
    report_dir: Path
    log_dir: Path
    telegram_offset_path: Path
    timezone: str
    log_level: str
    starting_equity: float
    auto_select_from_research: bool
    live_rollout: str
    risk: dict[str, float]
    data: dict[str, float | int | bool]
    execution: dict[str, float | int | bool]
    research: dict[str, int | float]
    mode: dict[str, list[str]]
    telegram: dict[str, str | bool]
    strategy_configs: dict[str, StrategyRuntimeConfig]
    bybit_api_key: str
    bybit_api_secret: str
    bybit_use_testnet: bool
    telegram_bot_token: str
    telegram_chat_id: str


def load_settings(explicit_root: str | None = None) -> Settings:
    repo_root = discover_repo_root(explicit_root)
    ensure_runtime_directories(repo_root)
    load_dotenv(repo_root / ".env", override=False)

    config_path = repo_root / "configs" / "settings.toml"
    if not config_path.exists():
        raise FileNotFoundError("configs/settings.toml 파일이 없습니다.")

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    strategy_configs: dict[str, StrategyRuntimeConfig] = {}
    for strategy_id, payload in raw["strategies"].items():
        strategy_configs[strategy_id] = StrategyRuntimeConfig(
            strategy_id=strategy_id,
            class_name=payload["class_name"],
            symbols=list(payload["symbols"]),
            timeframe=str(payload["timeframe"]),
            research_timeframes=list(payload.get("research_timeframes", [str(payload["timeframe"])])),
            priority=int(payload["priority"]),
            leverage=int(payload["leverage"]),
            enabled=bool(payload["enabled"]),
            demo_only=bool(payload.get("demo_only", False)),
            default_params=dict(payload.get("default_params", {})),
        )

    return Settings(
        repo_root=repo_root,
        database_path=repo_root / raw["system"]["database_path"],
        state_path=repo_root / raw["system"]["state_path"],
        market_dir=repo_root / raw["data"]["market_dir"],
        report_dir=repo_root / "reports",
        log_dir=repo_root / "logs",
        telegram_offset_path=repo_root / raw["telegram"]["offset_path"],
        timezone=str(raw["system"]["timezone"]),
        log_level=str(raw["system"]["log_level"]),
        starting_equity=float(raw["system"]["starting_equity"]),
        auto_select_from_research=bool(raw["system"]["auto_select_from_research"]),
        live_rollout=str(raw["system"]["live_rollout"]),
        risk=dict(raw["risk"]),
        data=dict(raw["data"]),
        execution=dict(raw["execution"]),
        research=dict(raw["research"]),
        mode={key: list(value) for key, value in raw["mode"].items()},
        telegram=dict(raw["telegram"]),
        strategy_configs=strategy_configs,
        bybit_api_key=os.getenv("BYBIT_API_KEY", "").strip(),
        bybit_api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
        bybit_use_testnet=os.getenv("BYBIT_USE_TESTNET", "true").lower() == "true",
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    )


def require_trading_credentials(settings: Settings) -> None:
    if not settings.bybit_api_key or not settings.bybit_api_secret:
        raise RuntimeError("Bybit API 키가 없습니다. .env 파일을 먼저 입력하세요.")
