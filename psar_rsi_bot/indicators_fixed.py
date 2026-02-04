from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


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
    ep = high[0] if bull else low[0]
    af = step

    for i in range(1, length):
        prev_sar = sar_values[-1] + af * (ep - sar_values[-1])
        if bull:
            prev_sar = min(prev_sar, low[i - 1], low[i - 2] if i > 1 else low[i - 1])
            if low[i] < prev_sar:
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


def compute_psar_rsi_ema(
    df: pd.DataFrame,
    ema_length: int = 200,
    rsi_length: int = 14,
    psar_step: float = 0.02,
    psar_max_step: float = 0.2,
    use_heikin_ashi: bool = True,
) -> pd.DataFrame:
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
        price_df = pd.DataFrame(
            {
                "open": ha_open,
                "high": ha_high,
                "low": ha_low,
                "close": ha_close,
            },
            index=out.index,
        )

    out["ema"] = ema(price_df["close"], ema_length)
    out["rsi"] = rsi(price_df["close"], length=rsi_length)
    psar_vals, psar_bull = parabolic_sar(price_df, step=psar_step, max_step=psar_max_step)
    out["psar"] = psar_vals
    out["psar_bull"] = psar_bull
    prev_trend = psar_bull.shift(1)
    if len(prev_trend) > 0:
        prev_trend.iloc[0] = psar_bull.iloc[0]
    prev_trend = prev_trend.astype(bool)
    out["psar_flip_long"] = (~prev_trend) & psar_bull
    out["psar_flip_short"] = prev_trend & (~psar_bull)
    return out
