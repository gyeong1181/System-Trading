from __future__ import annotations

from datetime import datetime, timedelta, timezone

from project.alerts import build_alert_message
from project.configuration import RiskConfig
from project.main import _seconds_until_next_cycle
from project.consensus import SignalDeduplicator, mark_optimal_signals
from project.risk import RiskAdvisor
from project.signals.models import Signal


def _make_signal(**kwargs) -> Signal:
    defaults = dict(
        symbol="BTCUSDT",
        direction="long",
        timeframe="15m",
        score=78,
        grade="추천",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        metadata={
            "momentum": 0.012,
            "trend_strength": 0.015,
            "atr": 45.0,
            "atr_pct": 0.008,
            "risk_reward": 2.1,
            "conditions": ["기술적 분석", "온체인/고래"],
            "summary": ["모멘텀 1.2%", "EMA 갭 1.5%"],
            "categories": {
                "기술적 분석": {"value": 82.0, "weight": 0.3, "notes": []},
                "온체인/고래": {"value": 74.0, "weight": 0.25, "notes": []},
            },
            "orderbook_bias": "매수벽 강함",
        },
    )
    defaults.update(kwargs)
    return Signal(**defaults)


def test_deduplicator_marks_duplicate_and_counts_direction() -> None:
    deduplicator = SignalDeduplicator(
        duplicate_window=timedelta(minutes=45),
        direction_window=timedelta(minutes=90),
    )
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    first = _make_signal(timestamp=now)
    deduplicator.apply([first], now)
    assert not first.is_duplicate
    assert first.signature_hits == 1
    assert first.direction_hits == 1

    later = now + timedelta(minutes=20)
    second = _make_signal(timestamp=later)
    deduplicator.apply([second], later)
    assert second.is_duplicate
    assert second.signature_hits == 2
    assert second.direction_hits == 2


def test_mark_optimal_and_formatting() -> None:
    advisor = RiskAdvisor(
        RiskConfig(base_leverage=5, max_leverage=7, bet_size_pct=7, risk_reward=2.1)
    )
    primary = _make_signal(symbol="BTCUSDT", score=86, grade="강력")
    secondary = _make_signal(symbol="ETHUSDT", score=70, grade="관심")
    signals = [primary, secondary]
    mark_optimal_signals(signals)

    # Manually set duplicate meta to mimic pipeline behaviour
    primary.direction_hits = 1
    secondary.direction_hits = 2
    secondary.signature_hits = 1
    secondary.is_duplicate = False

    message = build_alert_message(signals, advisor)
    assert "📢 BTCUSDT 롱 신호" in message
    assert "최적 신호: ✅" in message
    assert "기타 신호 요약" in message
    assert "중복 2회" in message
    assert "추천 레버리지" in message
    assert "근거 요약" in message


def test_seconds_until_next_cycle_aligns_to_shortest_timeframe() -> None:
    now = datetime(2024, 1, 1, 12, 7, 10, tzinfo=timezone.utc)
    wait = _seconds_until_next_cycle(["5m", "15m"], now=now)
    assert wait == 170


def test_seconds_until_next_cycle_respects_primary_interval() -> None:
    now = datetime(2024, 1, 1, 12, 7, 10, tzinfo=timezone.utc)
    wait = _seconds_until_next_cycle(["15m"], now=now)
    assert wait == 470


def test_seconds_until_next_cycle_enforces_minimum_wait() -> None:
    now = datetime(2024, 1, 1, 12, 5, tzinfo=timezone.utc)
    wait = _seconds_until_next_cycle(["5m"], now=now)
    assert wait == 30

