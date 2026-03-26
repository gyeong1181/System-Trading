from __future__ import annotations

import pandas as pd

from src.config import StrategyRuntimeConfig, load_settings
from strategies.donchian_breakout import DonchianBreakoutStrategy
from strategies.ema_rsi_trend import EmaRsiTrendStrategy


def make_frame(freq: str = "4h", periods: int = 240) -> pd.DataFrame:
    index = pd.date_range("2023-01-01", periods=periods, freq=freq)
    close = pd.Series([100 + i * 0.35 for i in range(periods)], index=index)
    frame = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.5,
            "low": close - 1.5,
            "close": close,
            "volume": 1000,
            "funding_rate": 0.0,
            "symbol": "ETHUSDT",
        },
        index=index,
    )
    return frame


def test_donchian_generates_regime_adx_and_cooldown_columns() -> None:
    strategy = DonchianBreakoutStrategy(
        StrategyRuntimeConfig(
            strategy_id="S1",
            class_name="DonchianBreakoutStrategy",
            symbols=["ETHUSDT"],
            timeframe="240",
            priority=1,
            leverage=2,
            enabled=True,
        )
    )
    signals = strategy.generate_signals(make_frame())
    assert {
        "ema_filter",
        "adx",
        "atr_regime_ratio",
        "break_even_trigger_distance",
        "entry_long",
        "entry_short",
        "stop_distance",
    } <= set(signals.columns)
    assert len(signals) > 0


def test_donchian_volatility_filter_can_block_entries() -> None:
    strategy = DonchianBreakoutStrategy(
        StrategyRuntimeConfig(
            strategy_id="S1",
            class_name="DonchianBreakoutStrategy",
            symbols=["ETHUSDT"],
            timeframe="240",
            priority=1,
            leverage=2,
            enabled=True,
        )
    )
    params = {**strategy.default_params(), "volatility_floor_ratio": 1.1}
    signals = strategy.generate_signals(make_frame(), params)
    assert signals["entry_long"].sum() == 0
    assert signals["entry_short"].sum() == 0


def test_ema_rsi_pullback_includes_time_stop_column() -> None:
    strategy = EmaRsiTrendStrategy(
        StrategyRuntimeConfig(
            strategy_id="S2",
            class_name="EmaRsiTrendStrategy",
            symbols=["ETHUSDT"],
            timeframe="240",
            priority=2,
            leverage=2,
            enabled=True,
        )
    )
    signals = strategy.generate_signals(make_frame())
    assert "time_stop_bars" in signals.columns
    assert signals["time_stop_bars"].iloc[-1] == strategy.default_params()["time_stop_bars"]


def test_s3_disabled_in_default_settings(repo_root) -> None:
    settings = load_settings(str(repo_root))
    assert settings.strategy_configs["S3"].enabled is False
