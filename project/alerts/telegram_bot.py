"""Telegram alert helper."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency path
    from telegram import Bot
    from telegram.error import TelegramError
except Exception:  # pragma: no cover - handled gracefully
    Bot = None  # type: ignore
    TelegramError = Exception  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class TelegramNotifier:
    token: Optional[str] = None
    chat_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.token is None:
            self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if self.chat_id is None:
            self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            logger.warning("Telegram notifier disabled - missing token or chat id")
            self._bot = None
            return

        if Bot is None:
            logger.warning("python-telegram-bot not installed; alerts will be logged only")
            self._bot = None
            return

        self._bot = Bot(self.token)

    def format_trade_alert(self, payload: Dict[str, object]) -> str:
        lines = [
            "🚨 Swing Signal Alert",
            f"Symbol      : {payload.get('symbol', 'N/A')}",
            f"Direction   : {payload.get('direction', 'N/A')}",
            f"Score       : {payload.get('score', 'N/A')}",
            f"Probability : {payload.get('probability', 'N/A')}%",
            f"Entry       : {payload.get('entry', 'N/A')}",
            f"Stop Loss   : {payload.get('stop', 'N/A')}",
            f"Take Profit : {payload.get('target', 'N/A')}",
            f"Position    : {payload.get('position_size', 'N/A')} units",
            f"Leverage    : x{payload.get('leverage', 'N/A')}",
        ]
        return "\n".join(lines)

    def send_trade_alert(self, payload: Dict[str, object]) -> None:
        message = self.format_trade_alert(payload)

        if self._bot is None:
            logger.info("[Telegram disabled] %s", message.replace("\n", " | "))
            return

        try:
            self._bot.send_message(chat_id=self.chat_id, text=message)
            logger.info("Telegram alert dispatched")
        except TelegramError as exc:  # pragma: no cover - requires network
            logger.error("Failed to send Telegram alert: %s", exc)


__all__ = ["TelegramNotifier"]
