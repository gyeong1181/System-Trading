"""Command line helper for the system trading project.

The CLI focuses on two lightweight tasks that unblock development:

* Inspect the project configuration to confirm expected symbols and options.
* Perform a quick data fetch or Telegram test notification to validate
  credentials before running heavier backtests.

Examples
--------
Fetch a short slice of OHLCV data using the default configuration::

    python -m project.main --fetch --limit 50

Send a Telegram test message (requires ``TELEGRAM_TOKEN`` and
``TELEGRAM_CHAT_ID`` environment variables)::

    python -m project.main --telegram-test --telegram-message "Ping"
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from project.alerts import TelegramNotifier
from project.data.binance_client import fetch_btc_eth_15m

try:  # pragma: no cover - exercised in integration usage
    import yaml
except ImportError:  # pragma: no cover - surfaced via a runtime error
    yaml = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


def _load_config(path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file if it exists."""
    if not path.exists():
        LOGGER.info("Configuration file %s not found; proceeding with defaults.", path)
        return {}

    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to load configuration files. Install it with 'pip install pyyaml'."
        )

    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp)  # type: ignore[arg-type]

    return data or {}


def _get_nested(config: Dict[str, Any], *path: str) -> Optional[Any]:
    cursor: Any = config
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def _summarise_config(config: Dict[str, Any]) -> str:
    mode = config.get("mode", "<missing>")
    symbols = config.get("symbols", {})
    btc_symbol = symbols.get("btc", "?") if isinstance(symbols, dict) else "?"
    eth_symbol = symbols.get("eth", "?") if isinstance(symbols, dict) else "?"
    timeframe = config.get("timeframe", "<missing>")
    dry_run = config.get("dry_run", True)
    return (
        f"Mode: {mode}, Symbols: BTC={btc_symbol}, ETH={eth_symbol}, "
        f"Timeframe: {timeframe}, Dry run: {dry_run}"
    )


def _configure_logging(verbosity: int) -> None:
    level = logging.INFO if verbosity == 0 else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


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
        default=120,
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
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity.")

    args = parser.parse_args(argv)

    _configure_logging(args.verbose)
    config = _load_config(args.config)
    LOGGER.info("Configuration summary: %s", _summarise_config(config))

    if args.fetch:
        LOGGER.info("Fetching OHLCV data (limit=%s)...", args.limit)
        data = fetch_btc_eth_15m(limit=args.limit)
        for symbol_alias, df in data.items():
            if df.empty:
                LOGGER.warning("%s: received no data rows", symbol_alias)
                continue
            first, last = df.index[0], df.index[-1]
            LOGGER.info(
                "%s: %s rows from %s to %s",
                symbol_alias,
                len(df),
                first.isoformat(),
                last.isoformat(),
            )

    if args.telegram_test:
        token = args.telegram_token or _get_nested(config, "alerts", "telegram", "token")
        if token is None:
            token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TG_TOKEN")

        chat_id = args.telegram_chat_id or _get_nested(config, "alerts", "telegram", "chat_id")
        if chat_id is None:
            chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT")

        parse_mode = _get_nested(config, "alerts", "telegram", "parse_mode")
        disable_notification = bool(_get_nested(config, "alerts", "telegram", "disable_notification") or False)

        if not token or not chat_id:
            LOGGER.error(
                "Telegram token/chat id missing. Provide them via the config, command line, or environment variables."
            )
            return 1

        LOGGER.info("Sending Telegram test alert to chat %s...", chat_id)
        notifier = TelegramNotifier(
            bot_token=str(token),
            chat_id=str(chat_id),
            parse_mode=parse_mode if isinstance(parse_mode, str) else None,
            disable_notification=disable_notification,
        )
        notifier.send_trade_alert(args.telegram_message)
        LOGGER.info("Telegram notification dispatched.")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
