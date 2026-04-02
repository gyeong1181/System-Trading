from __future__ import annotations

from typing import Any

import pandas as pd

from strategies.base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    display_name_ko = "돈치안 돌파"

    def default_params(self) -> dict[str, Any]:
        defaults = {
            "lookback": 35,
            "ema_filter_length": 200,
            "adx_length": 14,
            "adx_threshold": 20,
            "atr_length": 14,
            "atr_mult": 2.75,
            "cooldown_bars": 2,
            "break_even_trigger_atr": 1.0,
        }
        return {**defaults, **self.config.default_params}

    def param_grid(self) -> list[dict[str, Any]]:
        defaults = self.default_params()
        grid = []
        for lookback in [20, 25, 30, 35, 40, 45, 50]:
            exit_lookback = max(10, lookback // 2)
            volatility_window = max(50, lookback)
            for atr_mult in [2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5]:
                grid.append(
                    {
                        **defaults,
                        "lookback": lookback,
                        "exit_lookback": exit_lookback,
                        "volatility_window": volatility_window,
                        "volatility_floor_ratio": 1.0,
                        "atr_mult": atr_mult,
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
