"""Telegram notification helpers.

This module wraps ``python-telegram-bot``'s async ``Bot`` client with a small
utility that can be used from synchronous trading code.  The key behaviour is
that each alert ensures ``Bot.send_message`` is awaited so the coroutine is
actually executed under python-telegram-bot v20+.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send formatted trade alerts to a Telegram chat."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
    ) -> None:
        """Initialise the notifier with the Telegram bot token and chat id."""
        self._chat_id = chat_id
        self._parse_mode = parse_mode
        self._disable_notification = disable_notification
        self._bot = Bot(token=bot_token)

    async def _send_message(self, message: str) -> None:
        await self._bot.send_message(
            chat_id=self._chat_id,
            text=message,
            parse_mode=self._parse_mode,
            disable_notification=self._disable_notification,
        )

    def send_trade_alert(self, message: str) -> None:
        """Send a trade alert message to Telegram and await its completion."""

        async def _send_and_log() -> None:
            try:
                await self._send_message(message)
            except TelegramError as exc:
                logger.error("Failed to send Telegram trade alert.", exc_info=exc)
                raise

        try:
            asyncio.run(_send_and_log())
        except TelegramError:
            return
        except RuntimeError as exc:
            if "asyncio.run()" not in str(exc):
                raise

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_send_and_log())
            except TelegramError:
                return
            finally:
                loop.close()
