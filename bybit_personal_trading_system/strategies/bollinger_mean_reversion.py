from __future__ import annotations

from typing import Any

import pandas as pd

from strategies.base import BaseStrategy


class BollingerMeanReversionStrategy(BaseStrategy):
    display_name_ko = "볼린저 평균회귀"

    def default_params(self) -> dict[str, Any]:
        return {
            "length": 20,
            "band_mult": 2.2,
            "rsi_length": 14,
            "rsi_low": 35,
            "rsi_high": 65,
            "atr_length": 14,
            "atr_mult": 1.6,
        }

    def param_grid(self) -> list[dict[str, Any]]:
        return self.build_grid(
            {
                "length": [20, 30],
                "band_mult": [2.0, 2.3],
                "rsi_length": [14],
                "rsi_low": [30, 35],
                "rsi_high": [65, 70],
                "atr_length": [14],
                "atr_mult": [1.5, 1.8],
            }
        )

    def generate_signals(self, frame: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or self.default_params()
        data = frame.copy().sort_index()
        data["symbol"] = data.get("symbol", self.config.symbols[0])
        data["basis"] = data["close"].rolling(params["length"]).mean()
        data["std"] = data["close"].rolling(params["length"]).std(ddof=0)
        data["upper"] = data["basis"] + data["std"] * params["band_mult"]
        data["lower"] = data["basis"] - data["std"] * params["band_mult"]
        data["rsi"] = self.rsi(data["close"], params["rsi_length"])
        data["atr"] = self.atr(data, params["atr_length"])
        data["entry_long"] = (data["close"] < data["lower"]) & (data["rsi"] <= params["rsi_low"])
        data["entry_short"] = (data["close"] > data["upper"]) & (data["rsi"] >= params["rsi_high"])
        data["exit_long"] = data["close"] >= data["basis"]
        data["exit_short"] = data["close"] <= data["basis"]
        data["stop_distance"] = data["atr"] * params["atr_mult"]
        data["confidence"] = 0.54
        return data.dropna()
