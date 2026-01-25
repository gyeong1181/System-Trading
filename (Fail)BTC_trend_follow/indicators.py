from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    return true_range(df).ewm(alpha=1 / length, adjust=False).mean()


def dmi(df: pd.DataFrame, length: int):
    up_move = df["high"].diff()
    down_move = df["low"].shift(1) - df["low"]
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move

    tr = true_range(df)
    atr_series = tr.ewm(alpha=1 / length, adjust=False).mean()

    plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_series
    minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_series

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = (dx * 100).ewm(alpha=1 / length, adjust=False).mean()
    return plus_di.fillna(0), minus_di.fillna(0), adx.fillna(0)


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace({0: float("inf")})
    rsi_series = 100 - (100 / (1 + rs))
    return rsi_series.fillna(50)


def compute_indicators(
    df: pd.DataFrame,
    fast_len: int = 20,
    slow_len: int = 50,
    adx_len: int = 14,
    atr_len: int = 14,
) -> pd.DataFrame:
    if df.empty:
        return df

    output = df.copy()
    output["ema_fast"] = ema(output["close"], fast_len)
    output["ema_slow"] = ema(output["close"], slow_len)
    plus_di, minus_di, adx_series = dmi(output, adx_len)
    output["plus_di"] = plus_di
    output["minus_di"] = minus_di
    output["adx"] = adx_series
    output["atr"] = atr(output, atr_len)
    output["rsi"] = rsi(output["close"])
    return output
