"""Composite scoring for the reactive trading engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from project.data.context import AnalysisContext

FIB_LEVELS = (0.382, 0.5, 0.618, 0.786)
FIB_EXTENSION = (1.272, 1.618, 2.618)


@dataclass(frozen=True)
class CategoryScore:
    key: str
    label: str
    weight: float
    value: float
    notes: Tuple[str, ...]

    @property
    def weighted(self) -> float:
        return self.value * self.weight


@dataclass(frozen=True)
class CompositeScore:
    total: int
    bias: str
    categories: Dict[str, CategoryScore]
    conditions: Tuple[str, ...]
    momentum: float
    trend_strength: float
    atr: float
    atr_pct: float
    risk_reward: float
    summary: Tuple[str, ...]


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=max(1, period), adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    ups = delta.clip(lower=0)
    downs = -delta.clip(upper=0)
    avg_gain = ups.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = downs.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain.iloc[-1] / max(1e-9, avg_loss.iloc[-1])
    rsi = 100 - (100 / (1 + rs))
    return float(np.nan_to_num(rsi, nan=50.0))


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(np.nan_to_num(atr or 0.0, nan=0.0))


def _normalise(value: float, floor: float, ceiling: float) -> float:
    if ceiling == floor:
        return 0.5
    scaled = (value - floor) / (ceiling - floor)
    return float(np.clip(scaled, 0.0, 1.0))


def _nearest_fib(ratio: float) -> Tuple[float, float]:
    candidates = FIB_LEVELS + FIB_EXTENSION
    best = min(candidates, key=lambda level: abs(level - ratio))
    return best, abs(best - ratio)


def _fibonacci_notes(close: float, swing_high: float, swing_low: float) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if swing_high <= swing_low:
        return 0.5, notes
    retracement = (close - swing_low) / max(1e-9, swing_high - swing_low)
    level, distance = _nearest_fib(retracement)
    if level in FIB_LEVELS:
        notes.append(f"Fib retracement {level*100:.1f}%")
    else:
        notes.append(f"Fib extension {level*100:.1f}%")
    score = max(0.0, 1.0 - distance * 4)
    return score, notes


def _technical_category(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    context: AnalysisContext,
) -> Tuple[CategoryScore, float, float, float, float, List[str], Tuple[int, int]]:
    close = df["close"].astype(float)
    momentum = float((close.iloc[-1] - close.iloc[-10]) / close.iloc[-10]) if len(close) >= 10 else 0.0
    ema_fast = _ema(close, 21)
    ema_slow = _ema(close, 55)
    trend_strength = float((ema_fast.iloc[-1] - ema_slow.iloc[-1]) / max(1e-9, close.iloc[-1]))
    rsi = _rsi(close)
    atr = _atr(df)
    atr_pct = atr / max(1e-9, close.iloc[-1])

    swing_high = float(df["high"].astype(float).rolling(30).max().iloc[-1])
    swing_low = float(df["low"].astype(float).rolling(30).min().iloc[-1])
    fib_score, fib_notes = _fibonacci_notes(close.iloc[-1], swing_high, swing_low)

    momentum_score = _normalise(momentum, -0.04, 0.06) * 40
    trend_score = _normalise(trend_strength, -0.03, 0.04) * 30
    rsi_score = _normalise(rsi, 35, 65) * 15
    fib_bonus = fib_score * 10

    direction = "long" if momentum + trend_strength >= 0 else "short"
    confirmations = context.multi_timeframe_confirmation(symbol, timeframe, direction)
    mtf_bonus = 0.0
    if confirmations[1] > 0:
        mtf_bonus = (confirmations[0] / confirmations[1]) * 15

    orderbook_bias = context.heatmap_bias()
    heatmap_bonus = 5.0 if orderbook_bias == "Bid heavy" and direction == "long" else 0.0
    if orderbook_bias == "Ask heavy" and direction == "short":
        heatmap_bonus = 5.0

    total = momentum_score + trend_score + rsi_score + fib_bonus + mtf_bonus + heatmap_bonus
    value = float(np.clip(total, 0.0, 99.0))

    notes = [
        f"Momentum {momentum*100:.2f}%",
        f"EMA spread {trend_strength*100:.2f}%",
        f"RSI {rsi:.1f}",
        *fib_notes,
    ]
    if confirmations[1] > 0:
        notes.append(f"MTF confirmation {confirmations[0]}/{confirmations[1]}")
    notes.append(f"Orderbook {orderbook_bias}")

    category = CategoryScore(
        key="technical",
        label="Technical",
        weight=0.25,
        value=value,
        notes=tuple(notes),
    )
    return category, momentum, trend_strength, atr, atr_pct, notes, confirmations


def _onchain_category(external) -> CategoryScore:
    inflow = 1 - float(external.exchange_inflow_index)
    outflow = float(external.exchange_outflow_index)
    whale = float(external.whale_activity_index)
    mvrv = float(external.mvrv_zscore)
    mvrv_score = _normalise(-abs(mvrv), -5.0, 0.0)
    score = (
        inflow * 0.35
        + outflow * 0.25
        + whale * 0.25
        + mvrv_score * 0.15
    ) * 99
    notes = [
        f"Exchange outflow {outflow:.2f}",
        f"Whale activity {whale:.2f}",
        f"MVRV z-score {mvrv:.2f}",
    ]
    return CategoryScore(
        key="onchain",
        label="On-chain",
        weight=0.20,
        value=float(np.clip(score, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _micro_category(context: AnalysisContext) -> CategoryScore:
    ext = context.external
    funding = float(ext.funding_rate)
    oi = float(ext.open_interest_change)
    skew = float(ext.options_skew)
    max_pain = float(ext.max_pain_distance)
    heatmap = ext.orderbook_heatmap

    funding_score = _normalise(-abs(funding), -0.03, 0.0)
    oi_score = _normalise(oi, -0.1, 0.1)
    skew_score = _normalise(-abs(skew), -0.2, 0.0)
    max_pain_score = _normalise(-abs(max_pain), -0.15, 0.0)
    heatmap_score = _normalise(heatmap, 0.2, 0.8)

    combined = (
        funding_score * 0.2
        + oi_score * 0.25
        + skew_score * 0.2
        + max_pain_score * 0.15
        + heatmap_score * 0.2
    ) * 99
    notes = [
        f"Funding {funding:.4f}",
        f"OI change {oi:.2f}",
        f"Options skew {skew:.2f}",
        f"Max pain dist {max_pain:.2f}",
        f"Heatmap {heatmap:.2f}",
    ]
    return CategoryScore(
        key="microstructure",
        label="Microstructure",
        weight=0.15,
        value=float(np.clip(combined, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _sentiment_category(external) -> CategoryScore:
    fear = float(external.fear_greed)
    trends = float(external.google_trends)
    volume_sentiment = float(external.volume_sentiment)
    social = float(
        external.social_sentiment
        + external.twitter_sentiment
        + external.reddit_sentiment
        + external.telegram_sentiment
    ) / 4

    score = (
        _normalise(fear, 30, 80) * 0.4
        + _normalise(trends, 20, 90) * 0.25
        + volume_sentiment * 0.2
        + _normalise(social, -1.0, 1.0) * 0.15
    ) * 99
    notes = [
        f"Fear & Greed {fear:.1f}",
        f"Google trends {trends:.1f}",
        f"Volume sentiment {volume_sentiment:.2f}",
        f"Social sentiment {social:.2f}",
    ]
    return CategoryScore(
        key="sentiment",
        label="Sentiment",
        weight=0.15,
        value=float(np.clip(score, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _macro_category(external) -> CategoryScore:
    dxy = float(external.dxy_trend)
    rates = float(external.rates_trend)
    sp500 = float(external.sp500_trend)
    vix = float(external.vix_level)
    score = (
        _normalise(-dxy, -2.0, 2.0) * 0.3
        + _normalise(-rates, -1.5, 1.5) * 0.2
        + _normalise(sp500, -2.0, 2.0) * 0.3
        + _normalise(-vix, -10.0, 5.0) * 0.2
    ) * 99
    notes = [
        f"DXY trend {dxy:.2f}",
        f"Rates change {rates:.2f}",
        f"S&P500 change {sp500:.2f}",
        f"VIX level {vix:.2f}",
    ]
    return CategoryScore(
        key="macro",
        label="Macro",
        weight=0.10,
        value=float(np.clip(score, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _liquidity_category(context: AnalysisContext) -> CategoryScore:
    ext = context.external
    depth = float(ext.orderbook_heatmap)
    outflow = float(ext.exchange_outflow_index)
    volume_sentiment = float(ext.volume_sentiment)

    depth_score = _normalise(depth, 0.3, 0.7)
    outflow_score = _normalise(outflow, 0.3, 0.8)
    volume_score = _normalise(volume_sentiment, 0.3, 0.8)

    score = (depth_score * 0.4 + outflow_score * 0.35 + volume_score * 0.25) * 99
    notes = [
        f"Orderbook depth {depth:.2f}",
        f"Exchange outflow {outflow:.2f}",
        f"Volume sentiment {volume_sentiment:.2f}",
    ]
    return CategoryScore(
        key="liquidity",
        label="Liquidity",
        weight=0.05,
        value=float(np.clip(score, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _session_category(df: pd.DataFrame) -> CategoryScore:
    if df.index.tz is None:
        df = df.copy()
        df.index = pd.to_datetime(df.index, utc=True)
    timestamp = df.index[-1].to_pydatetime()
    hour = timestamp.hour
    session: str
    if 12 <= hour < 18:
        session = "US"
        base_score = 0.8
    elif 6 <= hour < 12:
        session = "EU"
        base_score = 0.65
    elif 0 <= hour < 6:
        session = "Asia"
        base_score = 0.55
    else:
        session = "Calm"
        base_score = 0.45

    close = df["close"].astype(float)
    recent_return = 0.0
    if len(close) >= 4:
        recent_return = float((close.iloc[-1] - close.iloc[-4]) / close.iloc[-4])
    return_score = _normalise(recent_return, -0.01, 0.015)

    value = float(np.clip((base_score * 0.7 + return_score * 0.3) * 99, 0.0, 99.0))
    notes = [
        f"Session {session}",
        f"Recent return {recent_return*100:.2f}%",
    ]
    return CategoryScore(
        key="session",
        label="Session Pattern",
        weight=0.05,
        value=value,
        notes=tuple(notes),
    )


def _consensus_category(external) -> CategoryScore:
    pro_bias = float(external.pro_trader_bias)
    score = _normalise(pro_bias, -1.0, 1.0) * 99
    notes = [f"Pro positioning {pro_bias:.2f}"]
    return CategoryScore(
        key="consensus",
        label="Pro Positioning",
        weight=0.05,
        value=float(np.clip(score, 0.0, 99.0)),
        notes=tuple(notes),
    )


def _derive_conditions(
    categories: Dict[str, CategoryScore],
    confirmations: Tuple[int, int],
    momentum: float,
    trend_strength: float,
) -> List[str]:
    conditions: List[str] = []
    for category in categories.values():
        if category.value >= 70:
            conditions.append(category.label)
    if confirmations[1] > 0 and confirmations[0] >= 1:
        conditions.append("MTF agreement")
    if momentum > 0 and trend_strength > 0:
        conditions.append("Momentum uptrend")
    if momentum < 0 and trend_strength < 0:
        conditions.append("Momentum downtrend")
    return conditions


def calculate_composite_score(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    context: AnalysisContext,
) -> CompositeScore:
    tech, momentum, trend_strength, atr, atr_pct, tech_notes, confirmations = _technical_category(
        symbol, timeframe, df, context
    )
    onchain = _onchain_category(context.external)
    micro = _micro_category(context)
    sentiment = _sentiment_category(context.external)
    macro = _macro_category(context.external)
    liquidity = _liquidity_category(context)
    session = _session_category(df)
    consensus = _consensus_category(context.external)

    categories = {
        tech.key: tech,
        onchain.key: onchain,
        micro.key: micro,
        sentiment.key: sentiment,
        macro.key: macro,
        liquidity.key: liquidity,
        session.key: session,
        consensus.key: consensus,
    }
    weighted_sum = sum(category.weighted for category in categories.values())
    total = int(np.clip(round(weighted_sum), 0, 99))

    bias = "long" if momentum + trend_strength >= 0 else "short"
    atr_pct_value = float(atr_pct)
    volatility = atr_pct_value
    trend_intensity = abs(momentum) * 120 + abs(trend_strength) * 80
    score_factor = max(0.5, total / 100)
    volatility_factor = max(0.6, min(2.5, 0.5 / max(0.005, volatility)))
    risk_reward = max(1.2, min(4.0, (trend_intensity + score_factor) * volatility_factor))

    summary: List[str] = []
    summary.extend(tech_notes[:2])
    summary.append(f"ATR {atr:.2f} ({atr_pct_value*100:.2f}%)")
    summary.append(onchain.notes[0])
    summary.append(micro.notes[0])

    conditions = _derive_conditions(categories, confirmations, momentum, trend_strength)

    return CompositeScore(
        total=total,
        bias=bias,
        categories=categories,
        conditions=tuple(conditions),
        momentum=float(momentum),
        trend_strength=float(trend_strength),
        atr=float(atr),
        atr_pct=atr_pct_value,
        risk_reward=float(risk_reward),
        summary=tuple(summary),
    )


def determine_grade(score: int) -> str:
    if score >= 88:
        return "강력"
    if score >= 75:
        return "우수"
    if score >= 65:
        return "기회"
    return "관망"


__all__ = ["CategoryScore", "CompositeScore", "calculate_composite_score", "determine_grade"]
