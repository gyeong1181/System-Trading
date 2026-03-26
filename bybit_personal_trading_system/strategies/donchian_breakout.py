from __future__ import annotations

from typing import Any

import pandas as pd

from strategies.base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    display_name_ko = "돈치안 돌파"

    def default_params(self) -> dict[str, Any]:
        return {
            "lookback": 30,
            "exit_lookback": 15,
            "ema_filter_length": 200,
            "adx_length": 14,
            "adx_threshold": 20,
            "volatility_window": 50,
            "volatility_floor_ratio": 1.0,
            "cooldown_bars": 3,
            "atr_length": 14,
            "atr_mult": 2.0,
            "break_even_trigger_atr": 0.0,
        }

    def param_grid(self) -> list[dict[str, Any]]:
        pair_templates = [
            {"lookback": 20, "exit_lookback": 10, "cooldown_bars": 2},
            {"lookback": 30, "exit_lookback": 10, "cooldown_bars": 3},
            {"lookback": 30, "exit_lookback": 15, "cooldown_bars": 3},
            {"lookback": 40, "exit_lookback": 15, "cooldown_bars": 4},
        ]
        regime_templates = [
            {"ema_filter_length": 150, "adx_length": 14, "adx_threshold": 18},
            {"ema_filter_length": 200, "adx_length": 14, "adx_threshold": 20},
        ]
        volatility_templates = [
            {"volatility_window": 50, "volatility_floor_ratio": 0.9},
            {"volatility_window": 50, "volatility_floor_ratio": 1.0},
            {"volatility_window": 50, "volatility_floor_ratio": 1.1},
        ]
        grid = []
        for pair in pair_templates:
            for regime in regime_templates:
                for volatility in volatility_templates:
                    for atr_mult in [2.0, 2.5, 3.0]:
                        for break_even_trigger_atr in [0.0, 1.0, 1.5]:
                            grid.append(
                                {
                                    **pair,
                                    **regime,
                                    **volatility,
                                    "atr_length": 14,
                                    "atr_mult": atr_mult,
                                    "break_even_trigger_atr": break_even_trigger_atr,
                                }
                            )
        return grid

    def generate_signals(self, frame: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or self.default_params()
        data = frame.copy().sort_index()
        data["symbol"] = data.get("symbol", self.config.symbols[0])
        data["donchian_high"] = data["high"].rolling(params["lookback"]).max().shift(1)
        data["donchian_low"] = data["low"].rolling(params["lookback"]).min().shift(1)
        data["exit_high"] = data["high"].rolling(params["exit_lookback"]).max().shift(1)
        data["exit_low"] = data["low"].rolling(params["exit_lookback"]).min().shift(1)
        data["atr"] = self.atr(data, params["atr_length"])
        data["ema_filter"] = self.ema(data["close"], params["ema_filter_length"])
        data["adx"] = self.adx(data, params["adx_length"])
        data["atr_baseline"] = data["atr"].rolling(int(params["volatility_window"])).median()
        data["atr_regime_ratio"] = data["atr"] / data["atr_baseline"].replace(0.0, pd.NA)
        volatility_ok = data["atr_regime_ratio"].fillna(0.0) >= float(params["volatility_floor_ratio"])

        raw_long = (
            (data["close"] > data["donchian_high"])
            & (data["close"] > data["ema_filter"])
            & (data["adx"] > params["adx_threshold"])
            & volatility_ok
        )
        raw_short = (
            (data["close"] < data["donchian_low"])
            & (data["close"] < data["ema_filter"])
            & (data["adx"] > params["adx_threshold"])
            & volatility_ok
        )

        entry_long = pd.Series(False, index=data.index)
        entry_short = pd.Series(False, index=data.index)
        last_entry_index = -10_000
        cooldown_bars = int(params["cooldown_bars"])
        for idx in range(len(data)):
            if idx - last_entry_index <= cooldown_bars:
                continue
            if bool(raw_long.iloc[idx]):
                entry_long.iloc[idx] = True
                last_entry_index = idx
            elif bool(raw_short.iloc[idx]):
                entry_short.iloc[idx] = True
                last_entry_index = idx

        data["entry_long"] = entry_long
        data["entry_short"] = entry_short
        data["exit_long"] = data["close"] < data["exit_low"]
        data["exit_short"] = data["close"] > data["exit_high"]
        data["stop_distance"] = data["atr"] * params["atr_mult"]
        data["break_even_trigger_distance"] = data["atr"] * float(params["break_even_trigger_atr"])
        data["confidence"] = 0.72
        return data.dropna()
