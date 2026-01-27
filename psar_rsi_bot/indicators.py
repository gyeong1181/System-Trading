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


def parabolic_sar(
    df: pd.DataFrame,
    step: float = 0.02,
    max_step: float = 0.2,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute Parabolic SAR values and the bullish/bearish trend flag.
    Returns:
        psar series, bull_trend series (True when SAR is below price).
    """
    if df.empty:
        empty = pd.Series(dtype=float)
        return empty, pd.Series(dtype=bool)

    high = df["high"].to_list()
    low = df["low"].to_list()
    close = df["close"].to_list()
    length = len(df)

    bull = True
    if length > 1:
        bull = close[1] >= close[0]

    sar_values = [low[0] if bull else high[0]]
    trend_flags = [bull]
    ep = high[0] if bull else low[0]  # extreme point
    af = step

    for i in range(1, length):
        prev_sar = sar_values[-1] + af * (ep - sar_values[-1])
        if bull:
            prev_sar = min(prev_sar, low[i - 1], low[i - 2] if i > 1 else low[i - 1])
            if low[i] < prev_sar:
                # flip to bearish
                bull = False
                sar = ep
                ep = low[i]
                af = step
            else:
                sar = prev_sar
                ep = max(ep, high[i])
                if ep == high[i]:
                    af = min(max_step, af + step)
        else:
            prev_sar = max(prev_sar, high[i - 1], high[i - 2] if i > 1 else high[i - 1])
            if high[i] > prev_sar:
                # flip to bullish
                bull = True
                sar = ep
                ep = high[i]
                af = step
            else:
                sar = prev_sar
                ep = min(ep, low[i])
                if ep == low[i]:
                    af = min(max_step, af + step)

        sar_values.append(sar)
        trend_flags.append(bull)

    psar_series = pd.Series(sar_values, index=df.index, dtype=float)
    bull_series = pd.Series(trend_flags, index=df.index, dtype=bool)
    return psar_series, bull_series


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


def compute_psar_rsi_ema(
    df: pd.DataFrame,
    ema_length: int = 200,
    rsi_length: int = 14,
    psar_step: float = 0.02,
    psar_max_step: float = 0.2,
    use_heikin_ashi: bool = True,
) -> pd.DataFrame:
    """
    Compute indicators required for the PSAR + RSI + EMA strategy.
    Adds columns:
    - ema: EMA of close
    - rsi: RSI of close
    - psar: Parabolic SAR value
    - psar_bull: True when SAR is under price (bullish)
    - psar_flip_long / psar_flip_short: True when PSAR flips direction on this bar
    """
    if df.empty:
        return df

    out = df.copy()
    price_df = out
    if use_heikin_ashi:
        ha_close = (out["open"] + out["high"] + out["low"] + out["close"]) / 4
        ha_open = ha_close.copy()
        ha_open.iloc[0] = (out["open"].iloc[0] + out["close"].iloc[0]) / 2
        for i in range(1, len(out)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
        ha_high = pd.concat([out["high"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = pd.concat([out["low"], ha_open, ha_close], axis=1).min(axis=1)
        out["ha_open"] = ha_open
        out["ha_high"] = ha_high
        out["ha_low"] = ha_low
        out["ha_close"] = ha_close
        price_df = out.rename(
            columns={
                "ha_open": "open",
                "ha_high": "high",
                "ha_low": "low",
                "ha_close": "close",
            }
        )[["open", "high", "low", "close"]]

    out["ema"] = ema(price_df["close"], ema_length)
    out["rsi"] = rsi(price_df["close"], length=rsi_length)
    psar_vals, psar_bull = parabolic_sar(price_df, step=psar_step, max_step=psar_max_step)
    out["psar"] = psar_vals
    out["psar_bull"] = psar_bull
    prev_trend = psar_bull.shift(1)
    # shift로 생기는 첫 NaN만 초기 추세로 채우고 bool로 명시 캐스팅
    if len(prev_trend) > 0:
        prev_trend.iloc[0] = psar_bull.iloc[0]
    prev_trend = prev_trend.astype(bool)
    out["psar_flip_long"] = (~prev_trend) & psar_bull
    out["psar_flip_short"] = prev_trend & (~psar_bull)
    return out
