"""Lightweight backtest utilities for the MVP."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    trades: int
    equity_curve: pd.Series


class BacktestEngine:
    def run(self, data: pd.DataFrame, signal_column: str = "signal") -> BacktestResult:
        if data.empty or signal_column not in data:
            raise ValueError("Data must contain a signal column for backtesting")

        close = data["close"].astype(float)
        returns = close.pct_change().fillna(0.0)
        positions = data[signal_column].shift(1).fillna(0.0)
        strategy_returns = returns * positions
        equity = (1 + strategy_returns).cumprod()

        total_return = float(equity.iloc[-1] - 1)
        daily_factor = 96 * 365  # 15-minute candles ≈ 96 per day
        sharpe = float(np.sqrt(daily_factor) * strategy_returns.mean() / (strategy_returns.std() + 1e-9))

        rolling_max = equity.cummax()
        drawdown = equity / rolling_max - 1
        max_dd = float(drawdown.min())

        trades = int((positions.diff().abs() > 0).sum())

        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            trades=trades,
            equity_curve=equity,
        )


__all__ = ["BacktestEngine", "BacktestResult"]
