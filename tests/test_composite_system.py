from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from project.data.context import AnalysisContext
from project.data.external import ExternalMetrics
from project.risk import RiskAdvisor
from project.risk.allocator import RiskRecommendation
from project.risk.controller import RiskController
from project.scoring import calculate_composite_score, determine_grade
from project.configuration import RiskConfig
from project.signals.models import Signal


def _make_dataframe(trend: float = 0.02) -> pd.DataFrame:
    idx = pd.date_range(end=datetime(2024, 1, 1, tzinfo=timezone.utc), periods=240, freq="5min")
    base = np.linspace(100, 100 * (1 + trend), len(idx))
    df = pd.DataFrame(
        {
            "open": base,
            "high": base + 1,
            "low": base - 1,
            "close": base,
            "volume": np.linspace(1000, 1500, len(idx)),
        },
        index=idx,
    )
    return df


def test_composite_scoring_conditions_and_grade() -> None:
    primary = _make_dataframe(trend=0.05)
    higher = _make_dataframe(trend=0.03)
    market_data = {"5m": {"BTCUSDT": primary}, "1h": {"BTCUSDT": higher}}
    metrics = ExternalMetrics(
        exchange_outflow_index=0.9,
        whale_activity_index=0.82,
        exchange_inflow_index=0.15,
        mvrv_zscore=-0.6,
        funding_rate=0.004,
        open_interest_change=0.1,
        options_skew=0.05,
        max_pain_distance=0.04,
        fear_greed=78,
        google_trends=80,
        volume_sentiment=0.68,
        social_sentiment=0.6,
        twitter_sentiment=0.55,
        reddit_sentiment=0.48,
        telegram_sentiment=0.5,
        dxy_trend=-0.7,
        rates_trend=-0.3,
        sp500_trend=0.6,
        vix_level=-4,
        pro_trader_bias=0.55,
        orderbook_heatmap=0.82,
    )
    context = AnalysisContext(market_data, metrics)
    score = calculate_composite_score("BTCUSDT", "5m", primary, context)
    assert score.total >= 70
    assert len(score.conditions) >= 2
    assert determine_grade(score.total) in {"관심", "추천", "강력"}
    assert score.risk_reward >= 1.5


def test_risk_advisor_and_controller(tmp_path) -> None:
    risk_config = RiskConfig(base_leverage=5, max_leverage=7, bet_size_pct=7, risk_reward=2.1)
    advisor = RiskAdvisor(risk_config)
    signal = Signal(
        symbol="BTCUSDT",
        direction="long",
        timeframe="15m",
        score=82,
        grade="추천",
        timestamp=datetime.now(timezone.utc),
        metadata={"atr_pct": 0.012, "risk_reward": 2.2},
    )
    recommendation = advisor.recommend(signal)
    assert recommendation.bet_pct == pytest.approx(risk_config.bet_size_pct, rel=0.01)
    controller = RiskController(
        tmp_path / "risk.json", daily_limit=10.0, weekly_limit=20.0
    )
    assert controller.can_execute(recommendation)
    controller.reserve(recommendation)
    controller.reserve(RiskRecommendation(leverage=5, bet_pct=3.0, risk_reward=2.0))
    assert not controller.can_execute(
        RiskRecommendation(leverage=5, bet_pct=0.5, risk_reward=2.0)
    )
