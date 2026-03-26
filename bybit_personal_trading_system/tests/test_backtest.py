from __future__ import annotations

import pandas as pd

from research.backtest import run_backtest
from src.config import StrategyRuntimeConfig
from strategies.donchian_breakout import DonchianBreakoutStrategy


def test_backtest_returns_metrics() -> None:
    index = pd.date_range("2023-01-01", periods=500, freq="4h")
    close = pd.Series([100 + i * 0.4 for i in range(500)], index=index)
    frame = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000,
            "funding_rate": 0.0,
            "symbol": "BTCUSDT",
        },
        index=index,
    )
    strategy = DonchianBreakoutStrategy(
        StrategyRuntimeConfig(
            strategy_id="S1",
            class_name="DonchianBreakoutStrategy",
            symbols=["BTCUSDT"],
            timeframe="240",
            priority=1,
            leverage=2,
            enabled=True,
        )
    )
    result = run_backtest(
        strategy=strategy,
        frame=frame,
        symbol="BTCUSDT",
        params=strategy.default_params(),
        fee_rate=0.0006,
        slippage=0.0005,
        risk_pct=0.007,
        starting_equity=280.0,
    )
    assert "total_return_pct" in result.metrics
    assert "max_drawdown_pct" in result.metrics
    assert result.equity_curve is not None


def test_break_even_stop_reduces_loss_after_favorable_move() -> None:
    index = pd.date_range("2023-01-01", periods=8, freq="4h")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 101.0, 104.0, 103.0, 101.0, 100.0, 100.0],
            "high": [101.0, 101.5, 104.5, 104.5, 103.5, 101.5, 100.5, 100.5],
            "low": [99.5, 99.8, 100.5, 102.5, 100.0, 99.5, 99.5, 99.5],
            "close": [100.0, 101.0, 104.0, 103.0, 101.0, 100.0, 100.0, 100.0],
            "volume": 1000,
            "funding_rate": 0.0,
            "symbol": "BTCUSDT",
        },
        index=index,
    )

    class StubStrategy:
        def generate_signals(self, frame, params):
            data = frame.copy()
            data["entry_long"] = False
            data["entry_short"] = False
            data["exit_long"] = False
            data["exit_short"] = False
            data["stop_distance"] = 2.0
            data["break_even_trigger_distance"] = 0.0
            data.iloc[1, data.columns.get_loc("entry_long")] = True
            data.iloc[1, data.columns.get_loc("break_even_trigger_distance")] = 2.0
            return data

    result = run_backtest(
        strategy=StubStrategy(),
        frame=frame,
        symbol="BTCUSDT",
        params={},
        fee_rate=0.0,
        slippage=0.0,
        risk_pct=0.01,
        starting_equity=100.0,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade["reason"] == "stop"
    assert trade["exit_price"] == trade["entry_price"]
