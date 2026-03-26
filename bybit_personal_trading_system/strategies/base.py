from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from src.config import StrategyRuntimeConfig
from src.models import TradeSignal


class BaseStrategy(ABC):
    display_name_ko = "전략"

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config

    @property
    def strategy_id(self) -> str:
        return self.config.strategy_id

    @staticmethod
    def ema(series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, length: int = 14) -> pd.Series:
        delta = series.diff()
        up = delta.clip(lower=0)
        down = (-delta).clip(lower=0)
        avg_gain = up.ewm(alpha=1 / length, adjust=False).mean()
        avg_loss = down.ewm(alpha=1 / length, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-12)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.where(avg_loss > 0, 100.0)
        rsi = rsi.where(avg_gain > 0, 0.0)
        return rsi

    @staticmethod
    def atr(frame: pd.DataFrame, length: int = 14) -> pd.Series:
        prev_close = frame["close"].shift(1)
        true_range = pd.concat(
            [
                (frame["high"] - frame["low"]).abs(),
                (frame["high"] - prev_close).abs(),
                (frame["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.ewm(alpha=1 / length, adjust=False).mean()

    @staticmethod
    def adx(frame: pd.DataFrame, length: int = 14) -> pd.Series:
        up_move = frame["high"].diff()
        down_move = -frame["low"].diff()
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=frame.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=frame.index,
        )
        atr = BaseStrategy.atr(frame, length).replace(0, np.nan)
        plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
        return dx.ewm(alpha=1 / length, adjust=False).mean().fillna(0.0)

    @abstractmethod
    def default_params(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def param_grid(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def generate_signals(self, frame: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.DataFrame:
        raise NotImplementedError

    def latest_signal(self, frame: pd.DataFrame, params: dict[str, Any] | None = None) -> TradeSignal | None:
        signals = self.generate_signals(frame, params)
        if signals.empty:
            return None
        row = signals.iloc[-1]
        bar_time = signals.index[-1]
        if isinstance(bar_time, pd.Timestamp):
            bar_time = bar_time.to_pydatetime()
        elif not isinstance(bar_time, datetime):
            bar_time = datetime.fromisoformat(str(bar_time))

        metadata = {"display_name_ko": self.display_name_ko, "params": params or self.default_params()}
        if bool(row["entry_long"]):
            stop_price = float(row["close"] - row["stop_distance"])
            return TradeSignal(
                strategy_id=self.strategy_id,
                symbol=str(row["symbol"]),
                timeframe=self.config.timeframe,
                action="entry",
                side="long",
                bar_time=bar_time,
                price=float(row["close"]),
                stop_price=stop_price,
                confidence=float(row.get("confidence", 0.5)),
                metadata=metadata,
            )
        if bool(row["entry_short"]):
            stop_price = float(row["close"] + row["stop_distance"])
            return TradeSignal(
                strategy_id=self.strategy_id,
                symbol=str(row["symbol"]),
                timeframe=self.config.timeframe,
                action="entry",
                side="short",
                bar_time=bar_time,
                price=float(row["close"]),
                stop_price=stop_price,
                confidence=float(row.get("confidence", 0.5)),
                metadata=metadata,
            )
        if bool(row["exit_long"]):
            return TradeSignal(
                strategy_id=self.strategy_id,
                symbol=str(row["symbol"]),
                timeframe=self.config.timeframe,
                action="exit",
                side="long",
                bar_time=bar_time,
                price=float(row["close"]),
                metadata=metadata,
            )
        if bool(row["exit_short"]):
            return TradeSignal(
                strategy_id=self.strategy_id,
                symbol=str(row["symbol"]),
                timeframe=self.config.timeframe,
                action="exit",
                side="short",
                bar_time=bar_time,
                price=float(row["close"]),
                metadata=metadata,
            )
        return None

    @staticmethod
    def build_grid(options: dict[str, list[Any]]) -> list[dict[str, Any]]:
        keys = list(options)
        return [dict(zip(keys, values)) for values in product(*(options[key] for key in keys))]
