from __future__ import annotations

from src.config import Settings

from strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy
from strategies.donchian_breakout import DonchianBreakoutStrategy
from strategies.ema_rsi_trend import EmaRsiTrendStrategy


STRATEGY_CLASS_MAP = {
    "DonchianBreakoutStrategy": DonchianBreakoutStrategy,
    "EmaRsiTrendStrategy": EmaRsiTrendStrategy,
    "BollingerMeanReversionStrategy": BollingerMeanReversionStrategy,
}


def build_strategy_registry(settings: Settings) -> dict[str, object]:
    registry: dict[str, object] = {}
    for strategy_id, config in settings.strategy_configs.items():
        if not config.enabled:
            continue
        strategy_class = STRATEGY_CLASS_MAP[config.class_name]
        registry[strategy_id] = strategy_class(config)
    return registry
