"""Reactive signal engine integrating event guards and persistence."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from project.alerts import build_alert_message
from project.consensus import SignalDeduplicator, mark_optimal_signals
from project.data.context import AnalysisContext
from project.data.external import ExternalMetrics, load_external_metrics
from project.data.score_tracker import ScoreTracker
from project.data.signal_repository import SignalRepository
from project.events.calendar import EventCalendar
from project.monitoring.outcome_tracker import OutcomeTracker
from project.risk import RiskAdvisor, RiskController
from project.risk.trade_plan import TradePlanBuilder
from project.risk.volatility import AtrGuard
from project.signals.generator import generate_signals
from project.signals.models import Signal

LOGGER = logging.getLogger(__name__)


class ReactiveEngine:
    """Coordinates the upgraded event-aware signal pipeline."""

    def __init__(
        self,
        *,
        symbols: dict[str, str],
        timeframes: list[str],
        client,
        notifier,
        score_tracker: ScoreTracker,
        repository: SignalRepository,
        outcome_tracker: OutcomeTracker,
        deduplicator: SignalDeduplicator,
        risk_advisor: RiskAdvisor,
        risk_controller: RiskController,
        atr_guard: AtrGuard,
        event_calendar: EventCalendar,
        trade_plan_builder: TradePlanBuilder,
        external_metrics_path: Optional[Path],
        data_limit: int,
        delta_threshold: float = 15.0,
        min_conditions: int = 2,
    ) -> None:
        self._symbols = symbols
        self._timeframes = timeframes
        self._client = client
        self._notifier = notifier
        self._data_limit = data_limit
        self._score_tracker = score_tracker
        self._repository = repository
        self._outcome_tracker = outcome_tracker
        self._deduplicator = deduplicator
        self._risk_advisor = risk_advisor
        self._risk_controller = risk_controller
        self._atr_guard = atr_guard
        self._event_calendar = event_calendar
        self._trade_plan_builder = trade_plan_builder
        self._external_metrics_path = external_metrics_path
        self._delta_threshold = delta_threshold
        self._min_conditions = min_conditions

    async def run_once(self) -> bool:
        now = datetime.now(timezone.utc)
        if self._event_calendar.is_blackout(now):
            LOGGER.info("Run aborted due to macro event blackout window.")
            self._repository.record(
                status="blackout",
                symbol=None,
                timeframe=None,
                direction=None,
                score=None,
                grade=None,
                delta=None,
                risk_reward=None,
                conditions=None,
                trade_plan=None,
                reasons=["macro_event_blackout"],
                metadata={"timestamp": now.isoformat()},
                created_at=now,
            )
            return False

        try:
            market_data = await asyncio.to_thread(
                fetch_timeframes,
                self._symbols,
                self._timeframes,
                limit=self._data_limit,
                client=self._client,
            )
        except Exception:
            LOGGER.exception("Failed to fetch market data.")
            return False

        external_metrics = await asyncio.to_thread(
            load_external_metrics,
            self._external_metrics_path,
        )
        context = AnalysisContext(market_data, external_metrics)

        candidates: List[Signal] = []
        for timeframe, per_symbol in market_data.items():
            candidates.extend(
                generate_signals(
                    per_symbol,
                    timeframe=timeframe,
                    as_of=now,
                    context=context,
                )
            )

        if not candidates:
            LOGGER.info("No candidate signals produced at %s.", now.isoformat())
            self._deduplicator.prune(now)
            return False

        self._deduplicator.apply(candidates, now)
        mark_optimal_signals(candidates)

        approved: List[Signal] = []
        for signal in candidates:
            snapshot = self._score_tracker.update(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                score=signal.score,
                when=now,
            )
            signal.metadata["score_delta"] = snapshot.delta
            signal.metadata["score_rolling"] = snapshot.rolling_avg
            reasons: List[str] = []
            if snapshot.delta < self._delta_threshold and len(signal.conditions) < self._min_conditions:
                reasons.append("insufficient_delta_conditions")

            risk_reward = float(signal.metadata.get("risk_reward", 0.0) or 0.0)
            if risk_reward < 1.5:
                reasons.append("risk_reward_below_min")

            atr_pct = float(signal.metadata.get("atr_pct", 0.0) or 0.0)
            if self._atr_guard.should_block(atr_pct):
                reasons.append("atr_spike")

            if signal.is_duplicate and not signal.is_optimal:
                reasons.append("duplicate_suppressed")

            if self._event_calendar.is_blackout(now, symbol=signal.symbol):
                reasons.append("symbol_blackout")

            recommendation = self._risk_advisor.recommend(signal)
            trade_plan = self._trade_plan_builder.build(signal, recommendation)
            signal.metadata["risk_recommendation"] = recommendation.as_dict()
            signal.metadata["trade_plan"] = trade_plan.as_dict()

            if not reasons and not self._risk_controller.can_execute(recommendation):
                LOGGER.info(
                    "Risk controller blocked %s %s due to drawdown state.",
                    signal.symbol,
                    signal.timeframe,
                )
                reasons.append("risk_controller_block")

            status = "sent" if not reasons else "filtered"
            if status == "sent":
                self._risk_controller.reserve(recommendation)

            record = self._repository.record(
                status=status,
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
                score=signal.score,
                grade=signal.grade,
                delta=snapshot.delta,
                risk_reward=risk_reward,
                conditions=signal.conditions,
                trade_plan=trade_plan.as_dict(),
                reasons=reasons,
                metadata=signal.metadata,
                created_at=now,
            )
            signal.metadata["signal_id"] = record.signal_id

            if status == "sent":
                self._outcome_tracker.schedule(record.signal_id, record.created_at)
                approved.append(signal)

        if not approved:
            LOGGER.info("All candidate signals filtered out at %s.", now.isoformat())
            self._risk_controller.persist()
            self._deduplicator.prune(now)
            return False

        payload = build_alert_message(approved)
        if not payload.strip():
            LOGGER.debug("Alert payload empty; skipping dispatch.")
            self._risk_controller.persist()
            self._deduplicator.prune(now)
            return False

        self._notifier.send_trade_alert(payload)
        self._risk_controller.persist()
        self._deduplicator.prune(now)
        return True


# Delayed import to avoid cycle during typing
from project.data.binance_client import fetch_timeframes  # noqa: E402
