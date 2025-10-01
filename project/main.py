"""Command line orchestrator for the automated BTC/ETH signal system."""
from __future__ import annotations

import argparse
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from project.alerts import TelegramNotifier, build_alert_message
from project.configuration import Settings, load_settings
from project.consensus import SignalDeduplicator, mark_optimal_signals
from project.data.binance_client import create_binance_client, fetch_timeframes
from project.risk import RiskAdvisor
from project.signals.generator import generate_signals

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
ENV_TOKEN_KEYS = ("TELEGRAM_TOKEN", "TG_TOKEN")
ENV_CHAT_KEYS = ("TELEGRAM_CHAT_ID", "TG_CHAT")


class LoggingNotifier:
    """Fallback notifier that only logs the alert payload."""

    def send_trade_alert(self, message: str) -> None:  # pragma: no cover - simple logging
        LOGGER.info("Alert skipped (no Telegram credentials). Message:\n%s", message)


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


def _timeframe_to_minutes(value: str) -> int:
    value = value.strip().lower()
    if value.endswith("m"):
        return max(1, int(value[:-1]))
    if value.endswith("h"):
        return max(1, int(value[:-1]) * 60)
    if value.endswith("d"):
        return max(1, int(value[:-1]) * 60 * 24)
    return max(1, int(value))


def _seconds_until_next_cycle(timeframes: list[str], now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    minutes = min(_timeframe_to_minutes(tf) for tf in timeframes)
    interval = max(60, minutes * 60)
    interval_delta = timedelta(seconds=interval)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = now - epoch
    remainder = elapsed % interval_delta
    wait_delta = interval_delta - remainder if remainder else timedelta(0)
    wait_seconds = max(30, math.ceil(wait_delta.total_seconds()))
    return wait_seconds


def _run_signal_cycle(
    *,
    settings: Settings,
    notifier: TelegramNotifier | LoggingNotifier,
    deduplicator: SignalDeduplicator,
    risk_advisor: RiskAdvisor,
    client,
) -> bool:
    as_of = datetime.now(timezone.utc)
    try:
        market_data = fetch_timeframes(
            settings.symbols,
            settings.runtime.timeframes,
            limit=settings.runtime.data_limit,
            client=client,
        )
    except Exception as exc:  # pragma: no cover - network failure
        LOGGER.exception("Failed to fetch market data: %s", exc)
        return False

    signals = []
    for timeframe, per_symbol in market_data.items():
        signals.extend(
            generate_signals(
                per_symbol,
                timeframe=timeframe,
                runtime=settings.runtime,
                as_of=as_of,
            )
        )

    if not signals:
        LOGGER.info("No qualifying signals at %s", as_of.isoformat())
        deduplicator.prune(as_of)
        return False

    deduplicator.apply(signals, as_of)
    mark_optimal_signals(signals)

    message = build_alert_message(signals, risk_advisor)
    if not message.strip():
        LOGGER.debug("Generated empty alert message; nothing to dispatch.")
        deduplicator.prune(as_of)
        return False

    notifier.send_trade_alert(message)
    LOGGER.info(
        "Dispatched %d signals across %d timeframes.",
        len(signals),
        len(settings.runtime.timeframes),
    )
    deduplicator.prune(as_of)
    return True


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
        "--skip-run",
        action="store_true",
        help="Skip the signal pipeline (useful for diagnostics).",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity.")

    args = parser.parse_args(argv)

    settings = load_settings(config_path=args.config)
    _configure_logging(settings.alerts.log_path, args.verbose)
    LOGGER.info("Configuration summary: %s", _summarise_settings(settings))

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
    client = create_binance_client()

    iterations = 0
    while True:
        try:
            _run_signal_cycle(
                settings=settings,
                notifier=notifier,
                deduplicator=deduplicator,
                risk_advisor=risk_advisor,
                client=client,
            )
        except Exception:  # pragma: no cover - defensive catch
            LOGGER.exception("Unexpected error during signal cycle.")

        iterations += 1
        if not args.run_loop:
            break
        if args.loop_iterations and iterations >= args.loop_iterations:
            break
        sleep_seconds = args.sleep_seconds or _seconds_until_next_cycle(settings.runtime.timeframes)
        LOGGER.debug("Sleeping %s seconds before next cycle...", sleep_seconds)
        time.sleep(sleep_seconds)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
