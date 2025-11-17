"""Telegram notification helpers.

This module wraps ``python-telegram-bot``'s async ``Bot`` client with a small
utility that can be used from synchronous trading code.  The key behaviour is
that each alert ensures ``Bot.send_message`` is awaited so the coroutine is
actually executed under python-telegram-bot v20+.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Iterable, Optional

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

    async def _send_payload(self, message: str, attachments: list[Path]) -> None:
        await self._bot.send_message(
            chat_id=self._chat_id,
            text=message,
            parse_mode=self._parse_mode,
            disable_notification=self._disable_notification,
        )
        for attachment in attachments:
            if not attachment.exists():
                logger.warning("Attachment missing on disk, skipping: %s", attachment)
                continue
            try:
                with attachment.open("rb") as handle:
                    await self._bot.send_document(
                        chat_id=self._chat_id,
                        document=handle,
                        filename=attachment.name,
                        disable_notification=self._disable_notification,
                    )
            except TelegramError as exc:
                logger.error("Failed to send attachment via Telegram: %s", attachment, exc_info=exc)

    def send_trade_alert(self, message: str, *, attachments: Optional[Iterable[Path]] = None) -> None:
        """Send a trade alert message (and optional attachments) to Telegram."""

        attachment_list = [Path(item) for item in attachments] if attachments else []

        async def _send_and_log() -> None:
            try:
                await self._send_payload(message, attachment_list)
            except TelegramError as exc:
                logger.error("Failed to send Telegram trade alert.", exc_info=exc)
                raise

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(_send_and_log())
            except TelegramError:
                return
            return

        task = loop.create_task(_send_and_log())

        def _log_task_result(done: asyncio.Future) -> None:
            try:
                done.result()
            except TelegramError:
                pass
            except asyncio.CancelledError:  # pragma: no cover - normal during shutdown
                logger.debug("Telegram notifier task cancelled before completion.")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Unexpected error in Telegram notifier task.", exc_info=exc)

        task.add_done_callback(_log_task_result)
