from __future__ import annotations

from typing import Any

import pandas as pd

from strategies.base import BaseStrategy


class EmaRsiTrendStrategy(BaseStrategy):
    display_name_ko = "EMA + RSI 눌림목"

    def default_params(self) -> dict[str, Any]:
        return {
            "ema_length": 200,
            "rsi_length": 14,
            "rsi_long_pullback": 40,
            "rsi_long_reentry": 50,
            "rsi_short_rebound": 60,
            "rsi_short_reentry": 50,
            "atr_length": 14,
            "atr_mult": 2.0,
            "time_stop_bars": 6,
        }

    def param_grid(self) -> list[dict[str, Any]]:
        threshold_templates = [
            {
                "rsi_long_pullback": 35,
                "rsi_long_reentry": 45,
                "rsi_short_rebound": 65,
                "rsi_short_reentry": 55,
            },
            {
                "rsi_long_pullback": 40,
                "rsi_long_reentry": 50,
                "rsi_short_rebound": 60,
                "rsi_short_reentry": 50,
            },
            {
                "rsi_long_pullback": 45,
                "rsi_long_reentry": 55,
                "rsi_short_rebound": 55,
                "rsi_short_reentry": 45,
            },
        ]
        grid = []
        for ema_length in [150, 200]:
            for threshold in threshold_templates:
                for atr_mult in [1.5, 2.0, 2.5]:
                    for time_stop_bars in [4, 6, 8]:
                        grid.append(
                            {
                                "ema_length": ema_length,
                                "rsi_length": 14,
                                **threshold,
                                "atr_length": 14,
                                "atr_mult": atr_mult,
                                "time_stop_bars": time_stop_bars,
                            }
                        )
        return grid

    def generate_signals(self, frame: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or self.default_params()
        data = frame.copy().sort_index()
        data["symbol"] = data.get("symbol", self.config.symbols[0])
        data["ema_filter"] = self.ema(data["close"], params["ema_length"])
        data["rsi"] = self.rsi(data["close"], params["rsi_length"])
        data["atr"] = self.atr(data, params["atr_length"])
        data["regime_long"] = data["close"] > data["ema_filter"]
        data["regime_short"] = data["close"] < data["ema_filter"]

        data["long_pullback_seen"] = (
            (data["regime_long"] & (data["rsi"] <= params["rsi_long_pullback"]))
            .rolling(3)
            .max()
            .shift(1)
            .fillna(0)
            .astype(bool)
        )
        data["short_rebound_seen"] = (
            (data["regime_short"] & (data["rsi"] >= params["rsi_short_rebound"]))
            .rolling(3)
            .max()
            .shift(1)
            .fillna(0)
            .astype(bool)
        )

        data["entry_long"] = (
            data["regime_long"]
            & data["long_pullback_seen"]
            & (data["rsi"] >= params["rsi_long_reentry"])
            & (data["close"] > data["close"].shift(1))
        )
        data["entry_short"] = (
            data["regime_short"]
            & data["short_rebound_seen"]
            & (data["rsi"] <= params["rsi_short_reentry"])
            & (data["close"] < data["close"].shift(1))
        )
        data["exit_long"] = (~data["regime_long"]) | (data["rsi"] >= params["rsi_short_rebound"])
        data["exit_short"] = (~data["regime_short"]) | (data["rsi"] <= params["rsi_long_pullback"])
        data["stop_distance"] = data["atr"] * params["atr_mult"]
        data["time_stop_bars"] = params["time_stop_bars"]
        data["confidence"] = 0.58
        return data.dropna()
