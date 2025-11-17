"""Command line orchestrator for the reactive BTC/ETH signal system."""
from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import shutil

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from project.alerts import TelegramNotifier
from project.analytics.performance import PerformanceAnalyzer
from project.configuration import Settings, load_settings
from project.consensus import SignalDeduplicator
from project.data.binance_client import create_binance_client, fetch_timeframes
from project.data.score_tracker import ScoreTracker
from project.data.signal_repository import SignalRepository
from project.events.calendar import EventCalendar
from project.monitoring.outcome_tracker import OutcomeTracker
from project.pipeline import ReactiveEngine
from project.reporting.performance_scheduler import PerformanceScheduler
from project.risk import RiskAdvisor
from project.risk.controller import RiskController
from project.risk.trade_plan import TradePlanBuilder
from project.risk.volatility import AtrGuard
from project.utils.timeframes import to_minutes

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
ENV_TOKEN_KEYS = ("TELEGRAM_TOKEN", "TG_TOKEN")
ENV_CHAT_KEYS = ("TELEGRAM_CHAT_ID", "TG_CHAT")


class LoggingNotifier:
    """Fallback notifier that only logs the alert payload."""

    def send_trade_alert(self, message: str, *, attachments: Optional[list[Path]] = None) -> None:  # pragma: no cover - simple logging
        LOGGER.info("Alert skipped (no Telegram credentials). Message:\n%s", message)
        if attachments:
            for item in attachments:
                LOGGER.info("Attachment available for manual review: %s", item)


def _summarise_settings(settings: Settings) -> str:
    symbol_part = ", ".join(f"{alias}={market}" for alias, market in settings.symbols.items())
    timeframe_part = ", ".join(settings.runtime.timeframes)
    return (
        f"Symbols: {symbol_part}; Timeframes: {timeframe_part}; "
        f"Min score: {settings.runtime.min_score}; Base lev: x{settings.risk.base_leverage:g}"
    )


def _configure_logging(log_path: Path, verbosity: int) -> None:
    level = logging.INFO if verbosity == 0 else logging.DEBUG
    handlers = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except OSError as exc:  # pragma: no cover - filesystem edge case
        LOGGER.warning("Failed to attach file logger: %s", exc)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def _resolve_env(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _build_notifier(
    settings: Settings,
    *,
    override_token: Optional[str] = None,
    override_chat_id: Optional[str] = None,
) -> TelegramNotifier | LoggingNotifier:
    token = override_token or settings.alerts.telegram_token or _resolve_env(*ENV_TOKEN_KEYS)
    chat_id = override_chat_id or settings.alerts.telegram_chat_id or _resolve_env(*ENV_CHAT_KEYS)
    if token and chat_id:
        return TelegramNotifier(
            bot_token=str(token),
            chat_id=str(chat_id),
            parse_mode=settings.alerts.parse_mode,
            disable_notification=settings.alerts.disable_notification,
        )
    LOGGER.warning("Telegram credentials missing; falling back to logging notifier.")
    return LoggingNotifier()


def _seconds_until_next_cycle(timeframes: list[str], now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    minutes = min(int(tf[:-1]) if tf.endswith("m") else to_minutes(tf) for tf in timeframes)
    interval = max(60, minutes * 60)
    interval_delta = timedelta(seconds=interval)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = now - epoch
    remainder = elapsed % interval_delta
    wait_delta = interval_delta - remainder if remainder else timedelta(0)
    wait_seconds = max(30, math.ceil(wait_delta.total_seconds()))
    return wait_seconds


def _locate_external_metrics(log_dir: Path) -> Optional[Path]:
    for suffix in ("yaml", "yml", "json"):
        candidate = log_dir / f"external_metrics.{suffix}"
        if candidate.exists():
            return candidate
    return None


def _handle_fetch(settings: Settings, limit: int) -> None:
    LOGGER.info("Fetching OHLCV data (limit=%s) for configured timeframes...", limit)
    client = create_binance_client()
    data = fetch_timeframes(settings.symbols, settings.runtime.timeframes, limit=limit, client=client)
    for timeframe, symbol_map in data.items():
        for symbol_alias, df in symbol_map.items():
            if df.empty:
                LOGGER.warning("%s %s: received no data rows", symbol_alias, timeframe)
                continue
            first, last = df.index[0], df.index[-1]
            LOGGER.info(
                "%s %s: %s rows from %s to %s",
                symbol_alias,
                timeframe,
                len(df),
                first.isoformat(),
                last.isoformat(),
            )


def _handle_telegram_test(
    settings: Settings,
    *,
    override_token: Optional[str],
    override_chat_id: Optional[str],
    message: str,
) -> None:
    notifier = _build_notifier(settings, override_token=override_token, override_chat_id=override_chat_id)
    notifier.send_trade_alert(message)
    LOGGER.info("Telegram notification dispatched for test message.")


async def _run_reactive_loop(
    engine: ReactiveEngine,
    *,
    timeframes: list[str],
    run_loop: bool,
    loop_iterations: int,
    sleep_seconds: int,
) -> None:
    iterations = 0
    while True:
        try:
            await engine.run_once()
        except Exception:  # pragma: no cover - defensive catch
            LOGGER.exception("Unexpected error during signal cycle.")

        iterations += 1
        if not run_loop:
            break
        if loop_iterations and iterations >= loop_iterations:
            break
        wait = sleep_seconds or _seconds_until_next_cycle(timeframes)
        LOGGER.debug("Sleeping %s seconds before next cycle...", wait)
        await asyncio.sleep(wait)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the YAML configuration file (default: %(default)s).",
    )
    parser.add_argument("--fetch", action="store_true", help="Fetch OHLCV data via ccxt.")
    parser.add_argument(
        "--limit",
        type=int,
        default=240,
        help="Number of candles to fetch when --fetch is supplied (default: %(default)s).",
    )
    parser.add_argument(
        "--telegram-test",
        action="store_true",
        help="Send a Telegram test alert using configuration or environment variables.",
    )
    parser.add_argument("--telegram-token", help="Override Telegram bot token for --telegram-test.")
    parser.add_argument("--telegram-chat-id", help="Override Telegram chat id for --telegram-test.")
    parser.add_argument(
        "--telegram-message",
        default="System trading notification test.",
        help="Message body used when --telegram-test is enabled.",
    )
    parser.add_argument(
        "--run-loop",
        action="store_true",
        help="Keep running the signal engine instead of a single cycle.",
    )
    parser.add_argument(
        "--loop-iterations",
        type=int,
        default=0,
        help="Limit the number of loop iterations when --run-loop is set (0 = infinite).",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=0,
        help="Override the sleep duration between loop iterations.",
    )
    parser.add_argument(
        "--event-calendar",
        type=Path,
        help="Optional path to a macro event blackout calendar file.",
    )
    parser.add_argument(
        "--delta-threshold",
        type=float,
        default=15.0,
        help="Minimum score delta required to dispatch a signal.",
    )
    parser.add_argument(
        "--atr-threshold",
        type=float,
        default=0.06,
        help="ATR percentage threshold that blocks signals (default: %(default)s).",
    )
    parser.add_argument(
        "--score-window-minutes",
        type=int,
        default=30,
        help="Rolling window (minutes) used for score delta calculations.",
    )
    parser.add_argument(
        "--atr-multiplier",
        type=float,
        default=1.0,
        help="ATR multiplier applied to trade plan projections (default: %(default)s).",
    )
    parser.add_argument(
        "--outcome-ttl-hours",
        type=int,
        default=6,
        help="Hours after which outcome tracking jobs evaluate alerts.",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip the signal pipeline (useful for diagnostics).",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Clear cached risk and signal data before running.",
    )
    parser.add_argument(
        "--analyze-performance",
        action="store_true",
        help="Run the performance analysis module and exit.",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity.")

    args = parser.parse_args(argv)

    settings = load_settings(config_path=args.config)
    _configure_logging(settings.alerts.log_path, args.verbose)
    LOGGER.info("Configuration summary: %s", _summarise_settings(settings))

    log_dir = settings.alerts.log_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    if args.reset_state:
        _reset_runtime_state(log_dir=log_dir, analysis_dir=settings.analysis.report_dir)
    if args.fetch:
        _handle_fetch(settings, args.limit)

    if args.telegram_test:
        _handle_telegram_test(
            settings,
            override_token=args.telegram_token,
            override_chat_id=args.telegram_chat_id,
            message=args.telegram_message,
        )

    if args.skip_run:
        return 0

    notifier = _build_notifier(settings)
    deduplicator = SignalDeduplicator(
        duplicate_window=timedelta(minutes=settings.runtime.duplicate_window_minutes),
        direction_window=timedelta(minutes=settings.runtime.direction_window_minutes),
    )
    risk_advisor = RiskAdvisor(settings.risk)

    score_tracker = ScoreTracker(
        log_dir / "score_tracker.json",
        window=timedelta(minutes=max(1, args.score_window_minutes)),
    )
    repository = SignalRepository(log_dir / "signals.sqlite")
    risk_controller = RiskController(
        log_dir / "risk_state.json",
        daily_limit=settings.risk.daily_loss_limit,
        weekly_limit=settings.risk.weekly_loss_limit,
        reservation_ttl_hours=settings.risk.reservation_ttl_hours,
        limits_enabled=settings.risk.limits_enabled,
    )
    if not settings.risk.limits_enabled:
        LOGGER.warning("Risk drawdown limits disabled; all signals will bypass loss caps.")
    outcome_tracker = OutcomeTracker(
        repository,
        ttl_hours=max(1, args.outcome_ttl_hours),
        symbols=settings.symbols,
        risk_controller=risk_controller,
    )
    trade_plan_builder = TradePlanBuilder(atr_multiplier=args.atr_multiplier)
    atr_guard = AtrGuard(hold_threshold=args.atr_threshold)
    event_calendar_path = args.event_calendar or (log_dir / "event_calendar.yaml")
    event_calendar = EventCalendar.from_file(event_calendar_path)
    external_metrics_path = _locate_external_metrics(log_dir)
    client = create_binance_client()

    performance_analyzer = None
    performance_scheduler = None
    if args.analyze_performance or settings.analysis.enabled:
        performance_analyzer = PerformanceAnalyzer(
            database_path=repository.database_path,
            report_dir=settings.analysis.report_dir,
            notifier=notifier,
            notify_summary=settings.analysis.notify_summary,
        )
    if settings.analysis.enabled:
        performance_scheduler = PerformanceScheduler(
            state_path=settings.analysis.report_dir / "analysis_state.json",
            interval=timedelta(hours=settings.analysis.interval_hours),
            min_new_signals=settings.analysis.min_new_signals,
        )

    if args.analyze_performance and performance_analyzer:
        performance_analyzer.run()
        repository.close()
        return 0

    engine = ReactiveEngine(
        symbols=settings.symbols,
        timeframes=settings.runtime.timeframes,
        client=client,
        notifier=notifier,
        runtime=settings.runtime,
        score_tracker=score_tracker,
        repository=repository,
        outcome_tracker=outcome_tracker,
        deduplicator=deduplicator,
        risk_advisor=risk_advisor,
        risk_controller=risk_controller,
        atr_guard=atr_guard,
        event_calendar=event_calendar,
        trade_plan_builder=trade_plan_builder,
        external_metrics_path=external_metrics_path,
        data_limit=settings.runtime.data_limit,
        delta_threshold=args.delta_threshold,
        min_conditions=2,
        performance_analyzer=performance_analyzer if settings.analysis.enabled else None,
        performance_scheduler=performance_scheduler if settings.analysis.enabled else None,
    )

    try:
        asyncio.run(
            _run_reactive_loop(
                engine,
                timeframes=settings.runtime.timeframes,
                run_loop=args.run_loop,
                loop_iterations=args.loop_iterations,
                sleep_seconds=args.sleep_seconds,
            )
        )
    finally:
        repository.close()

    return 0


def _reset_runtime_state(*, log_dir: Path, analysis_dir: Path) -> None:
    targets = [
        log_dir / "risk_state.json",
        log_dir / "score_tracker.json",
        log_dir / "signals.sqlite",
        log_dir / "signals.sqlite-wal",
        log_dir / "signals.sqlite-shm",
    ]
    for path in targets:
        try:
            if path.exists():
                path.unlink()
                LOGGER.info("Removed %s", path)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            LOGGER.warning("Failed to remove %s: %s", path, exc)

    try:
        if analysis_dir.exists():
            shutil.rmtree(analysis_dir)
            LOGGER.info("Removed analysis directory %s", analysis_dir)
    except Exception as exc:  # pragma: no cover - best effort cleanup
        LOGGER.warning("Failed to remove analysis directory %s: %s", analysis_dir, exc)



if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
