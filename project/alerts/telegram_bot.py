"""Telegram notification helpers.

This module wraps ``python-telegram-bot``'s async ``Bot`` client with a small
utility that can be used from synchronous trading code.  The key behaviour is
that each alert ensures ``Bot.send_message`` is awaited so the coroutine is
actually executed under python-telegram-bot v20+.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Coroutine, Optional

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

    def _run_in_background_loop(
        self, coro_factory: Callable[[], Coroutine[object, object, None]]
    ) -> None:
        """Execute ``coro_factory`` in a fresh event loop on a worker thread."""

        error: Optional[BaseException] = None

        def _runner() -> None:
            nonlocal error
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro_factory())
            except BaseException as exc:  # pragma: no cover - defensive guard
                error = exc
            finally:
                loop.close()

        thread = threading.Thread(target=_runner, name="TelegramNotifierLoop")
        thread.start()
        thread.join()

        if error is None:
            return

        if isinstance(error, TelegramError):
            # The coroutine already logged the failure.
            return

        raise error

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

            self._run_in_background_loop(_send_and_log)
